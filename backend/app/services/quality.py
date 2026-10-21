"""Bloqueios e qualidade (E4).

- Bloqueios atuais: `isBlocked`, `blockReason` e `currentBlockTimeSeconds` (API) dos cartões ativos em aberto.
- Histórico de bloqueios: eventos `field_change` de `isBlocked` observados nas syncs (precisão = intervalo de sync).
- Reaberturas: passagem de `done` para backlog/todo/in_progress, observada nas syncs ou nas transições da API.
"""

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
from typing import Any

from pymongo.database import Database

from app.repositories.base import utcnow
from app.services.card_query import CLOSED_STATUSES, CardEnricher, CardFilters, build_query
from app.services.delivery import completed_query
from app.services.flow import summarize
from app.services.history import history_since
from app.services.periods import Granularity, Period, bucket_label, bucket_of, buckets

MAX_ITEMS = 500
OPEN_STATUSES = ("backlog", "todo", "in_progress")
NO_REASON = "Sem motivo"


def _matching_ids(db: Database, board_id: int, filters: CardFilters, period: Period, now: datetime) -> set[int]:
    """Cartões (qualquer estado, incluindo em falta) que cumprem os filtros com os atributos atuais."""
    f = replace(
        filters,
        state="all",
        status=[],
        blocked=None,
        overdue=False,
        due_soon=False,
        created_from=None,
        created_to=None,
        ended_from=None,
        ended_to=None,
        include_missing=True,
    )
    return set(db.cards.distinct("cardId", build_query(board_id, f, period.tz, now)))


def _dist(items: list[tuple[Any, str, float]]) -> list[dict[str, Any]]:
    """(chave, rótulo, dias) → [{key, label, count, days}] por contagem desc."""
    count: Counter = Counter()
    days: Counter = Counter()
    labels: dict[Any, str] = {}
    for key, label, d in items:
        count[key] += 1
        days[key] += d
        labels[key] = label
    return [{"key": k, "label": labels[k], "count": n, "days": round(days[k], 2)} for k, n in count.most_common()]


def _series(period: Period, granularity: Granularity, counters: dict[str, Counter]) -> list[dict[str, Any]]:
    return [
        {"bucket": b.isoformat(), "label": bucket_label(b, granularity)} | {name: c.get(b, 0) for name, c in counters.items()}
        for b in buckets(period, granularity)
    ]


def build_blockers(
    db: Database,
    board: dict[str, Any],
    filters: CardFilters,
    period: Period,
    granularity: Granularity,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    board_id = board["boardId"]
    enrich = CardEnricher(db, board, now)

    base = replace(filters, state="active", status=[], blocked=None)
    open_query = {"$and": [build_query(board_id, base, period.tz, now), {"status": {"$nin": CLOSED_STATUSES}}]}
    open_total = db.cards.count_documents(open_query)
    blocked = list(db.cards.find({"$and": [open_query, {"isBlocked": True}]}, {"_id": 0}))
    blocked.sort(key=lambda c: -(c.get("currentBlockTimeSeconds") or 0))

    items = []
    for c in blocked:
        seconds = c.get("currentBlockTimeSeconds")
        reason = c.get("blockReason") or {}
        items.append(
            {
                "cardId": c["cardId"],
                "customId": c.get("customId"),
                "title": c.get("title"),
                "status": c.get("status"),
                "columnId": c.get("columnId"),
                "columnName": enrich.column_name(c.get("columnId")),
                "laneName": enrich.lanes.get(c.get("laneId")),
                "ownerUserId": c.get("ownerUserId"),
                "ownerName": enrich.user(c.get("ownerUserId")),
                "reason": reason.get("label") or (f"Motivo {reason['reasonId']}" if reason.get("reasonId") else None),
                "comment": reason.get("comment"),
                "blockedSeconds": seconds,
                "blockedDays": round(seconds / 86400, 2) if seconds is not None else None,
            }
        )
    days_of = lambda i: i["blockedDays"] or 0  # noqa: E731
    current_days = [i["blockedDays"] for i in items if i["blockedDays"] is not None]

    # Histórico observado nas syncs.
    allowed = _matching_ids(db, board_id, filters, period, now)
    started: Counter = Counter()
    resolved: Counter = Counter()
    durations: list[float] = []
    open_since: dict[int, datetime] = {}
    events = db.card_events.find(
        {"boardId": board_id, "source": "sync", "field": "isBlocked", "occurredAt": {"$lt": period.end_utc}},
        {"_id": 0, "cardId": 1, "to": 1, "occurredAt": 1},
    ).sort("occurredAt", 1)
    for e in events:
        if e["cardId"] not in allowed:
            continue
        at = e["occurredAt"]
        if e.get("to"):
            open_since[e["cardId"]] = at
            if period.contains(at):
                started[bucket_of(at, granularity, period.tz)] += 1
        else:
            start = open_since.pop(e["cardId"], None)
            if period.contains(at):
                resolved[bucket_of(at, granularity, period.tz)] += 1
                if start is not None:
                    durations.append((at - start).total_seconds() / 86400)

    return {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": granularity},
        "current": {
            "blocked": len(items),
            "openTotal": open_total,
            "share": round(len(items) / open_total, 4) if open_total else None,
            "days": summarize(current_days, "sem cartões bloqueados"),
            "byReason": _dist([(i["reason"] or NO_REASON, i["reason"] or NO_REASON, days_of(i)) for i in items]),
            "byOwner": _dist([(i["ownerUserId"], i["ownerName"] or "Sem responsável", days_of(i)) for i in items]),
            "byColumn": _dist([(i["columnId"], i["columnName"] or "—", days_of(i)) for i in items]),
            "items": items[:MAX_ITEMS],
            "truncated": len(items) > MAX_ITEMS,
        },
        "history": {
            "historySince": history_since(db, board_id)["snapshotsSince"],
            "started": sum(started.values()),
            "resolved": sum(resolved.values()),
            "resolvedDays": summarize(durations, "sem desbloqueios observados no período"),
            "series": _series(period, granularity, {"started": started, "resolved": resolved}),
        },
    }


def _reopen_events(db: Database, board_id: int, period: Period) -> list[dict[str, Any]]:
    return list(
        db.card_events.find(
            {
                "boardId": board_id,
                "occurredAt": {"$gte": period.start_utc, "$lt": period.end_utc},
                "$or": [
                    {"source": "sync", "field": "status", "from": "done", "to": {"$in": list(OPEN_STATUSES)}},
                    {"source": "api", "type": "transition", "fromStatus": "done", "toStatus": {"$in": list(OPEN_STATUSES)}},
                ],
            },
            {"_id": 0, "cardId": 1, "source": 1, "occurredAt": 1, "to": 1, "toStatus": 1},
        )
    )


def build_quality(
    db: Database,
    board: dict[str, Any],
    filters: CardFilters,
    period: Period,
    granularity: Granularity,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    board_id = board["boardId"]
    enrich = CardEnricher(db, board, now)
    allowed = _matching_ids(db, board_id, filters, period, now)

    # A mesma reabertura pode ser vista pela sync e pelas transições da API:
    # por cartão conta a fonte com mais ocorrências.
    per_card: dict[int, dict[str, list[datetime]]] = defaultdict(lambda: {"sync": [], "api": []})
    for e in _reopen_events(db, board_id, period):
        if e["cardId"] in allowed:
            per_card[e["cardId"]][e["source"]].append(e["occurredAt"])
    series: Counter = Counter()
    reopened = []
    for card_id, by_source in per_card.items():
        times = max(by_source.values(), key=len)
        for t in times:
            series[bucket_of(t, granularity, period.tz)] += 1
        reopened.append((card_id, len(times), max(by_source["sync"] + by_source["api"])))

    cards = {
        c["cardId"]: c
        for c in db.cards.find({"boardId": board_id, "cardId": {"$in": [r[0] for r in reopened]}}, {"_id": 0})
    }
    items = sorted(
        (
            {
                "cardId": card_id,
                "customId": cards.get(card_id, {}).get("customId"),
                "title": cards.get(card_id, {}).get("title"),
                "status": cards.get(card_id, {}).get("status"),
                "columnName": enrich.column_name(cards.get(card_id, {}).get("columnId")),
                "ownerName": enrich.user(cards.get(card_id, {}).get("ownerUserId")),
                "reopens": n,
                "lastReopenedAt": last,
            }
            for card_id, n, last in reopened
        ),
        key=lambda i: (-i["reopens"], -i["lastReopenedAt"].timestamp()),
    )
    completed = db.cards.count_documents(completed_query(board_id, filters, period, now))
    since = history_since(db, board_id)["snapshotsSince"]
    result: dict[str, Any] = {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": granularity},
        "historySince": since,
        "available": since is not None or bool(items),
        "reopens": sum(i["reopens"] for i in items),
        "reopenedCards": len(items),
        "completed": completed,
        "reopenRate": round(len(items) / completed, 4) if completed else None,
        "series": _series(period, granularity, {"reopens": series}),
        "items": items[:MAX_ITEMS],
        "truncated": len(items) > MAX_ITEMS,
    }
    if not result["available"]:
        result["reason"] = "recolha de histórico ainda não iniciada"
    return result
