"""Dashboard geral (README §5.2): KPIs do estado atual, distribuições e evolução criados/concluídos."""

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from pymongo.database import Database

from app.models.cards import PRIORITY_LABELS, STATUS_LABELS
from app.repositories.base import utcnow
from app.services.card_query import DUE_SOON_DAYS, CardEnricher, CardFilters, build_query
from app.services.periods import Granularity, Period, bucket_label, bucket_of, buckets

FIELDS = {
    "_id": 0,
    "cardId": 1,
    "status": 1,
    "columnId": 1,
    "laneId": 1,
    "typeId": 1,
    "priority": 1,
    "ownerUserId": 1,
    "isBlocked": 1,
    "deadline": 1,
    "createdAt": 1,
    "endTime": 1,
    "size": 1,
}
OPEN_EXCLUDED = {"done", "archived", "discarded"}


def _dist(counter: Counter, labels: dict[Any, str | None], order: list[Any] | None = None, fallback: str = "—") -> list[dict[str, Any]]:
    keys = [k for k in (order or []) if k in counter] + sorted((k for k in counter if k not in (order or [])), key=lambda k: -counter[k])
    return [{"key": k, "label": labels.get(k) or fallback, "count": counter[k]} for k in keys]


def build_dashboard(
    db: Database,
    board: dict[str, Any],
    filters: CardFilters,
    period: Period,
    granularity: Granularity,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    board_id = board["boardId"]
    tz = period.tz
    enrich = CardEnricher(db, board, now)
    current = list(db.cards.find(build_query(board_id, filters, tz, now), FIELDS))

    def count(pred) -> int:
        return sum(1 for c in current if pred(c))

    open_ = lambda c: c.get("status") not in OPEN_EXCLUDED  # noqa: E731
    soon = now + timedelta(days=DUE_SOON_DAYS)
    kpis = {
        "total": len(current),
        "backlog": count(lambda c: c.get("status") == "backlog"),
        "todo": count(lambda c: c.get("status") == "todo"),
        "inProgress": count(lambda c: c.get("status") == "in_progress"),
        "active": count(lambda c: c.get("status") in ("todo", "in_progress")),
        "done": count(lambda c: c.get("status") == "done"),
        "blocked": count(lambda c: c.get("isBlocked")),
        "overdue": count(lambda c: open_(c) and c.get("deadline") and c["deadline"] < now),
        "dueSoon": count(lambda c: open_(c) and c.get("deadline") and now <= c["deadline"] < soon),
        "unassigned": count(lambda c: c.get("ownerUserId") is None),
    }

    # Evolução: inclui arquivados (os concluídos acabam por ser arquivados); ignora filtros de estado/datas.
    period_filters = replace(filters, state="all", status=[], created_from=None, created_to=None, ended_from=None, ended_to=None)
    base = build_query(board_id, period_filters, tz, now)
    created = list(db.cards.find({**base, "createdAt": {"$gte": period.start_utc, "$lt": period.end_utc}}, {"createdAt": 1}))
    completed = list(db.cards.find({**base, "endTime": {"$gte": period.start_utc, "$lt": period.end_utc}}, {"endTime": 1, "size": 1}))
    created_by = Counter(bucket_of(c["createdAt"], granularity, tz) for c in created)
    completed_by = Counter(bucket_of(c["endTime"], granularity, tz) for c in completed)
    timeline = [
        {"bucket": b.isoformat(), "label": bucket_label(b, granularity), "created": created_by[b], "completed": completed_by[b]}
        for b in buckets(period, granularity)
    ]
    kpis["createdInPeriod"] = len(created)
    kpis["completedInPeriod"] = len(completed)

    column_order = [c["columnId"] for c in (board.get("structure") or {}).get("columns", [])]
    column_labels = {cid: enrich.column_name(cid) for cid in column_order}
    owners = Counter(c.get("ownerUserId") for c in current)
    return {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "generatedAt": now,
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": granularity},
        "kpis": kpis,
        "distributions": {
            "status": _dist(Counter(c.get("status") for c in current), STATUS_LABELS, list(STATUS_LABELS)),
            "column": _dist(Counter(c.get("columnId") for c in current), column_labels, column_order),
            "lane": _dist(Counter(c.get("laneId") for c in current), enrich.lanes, list(enrich.lanes)),
            "type": _dist(Counter(c.get("typeId") for c in current), enrich.types, fallback="Sem tipo"),
            "priority": _dist(Counter(c.get("priority") for c in current), PRIORITY_LABELS, list(PRIORITY_LABELS)),
            "owner": _dist(owners, {u: enrich.user(u) for u in owners if u is not None}, fallback="Sem responsável"),
        },
        "timeline": timeline,
    }
