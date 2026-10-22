"""Página Atenção (D6): triagem diária do tech lead — cartões e pessoas que exigem ação agora.

Motivos de atenção (cartões abertos, estado atual):
- `blocked`: cartão bloqueado;
- `overdue`: prazo ultrapassado;
- `aging`: em curso há mais tempo do que o P85 do cycle time dos cartões concluídos no período;
- `dueSoon`: prazo nos próximos `DUE_SOON_DAYS` dias;
- `unassigned`: a fazer ou em curso sem responsável.
Pessoas com mais cartões em curso do que `ATTENTION_WIP_PER_PERSON` são sinalizadas (WIP alto).
"""

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from pymongo.database import Database

from app.models.cards import STATUS_LABELS
from app.repositories.base import utcnow
from app.services.card_query import CLOSED_STATUSES, DUE_SOON_DAYS, CardEnricher, CardFilters, aging_days, build_query
from app.services.delivery import completed_query
from app.services.flow import SMALL_SAMPLE, percentile
from app.services.periods import Period
from app.services.quality import build_quality

MAX_ITEMS = 300
DAY = 86400
# Peso de cada motivo na ordenação (mais urgente primeiro).
WEIGHTS = {"blocked": 8, "overdue": 8, "aging": 4, "dueSoon": 2, "unassigned": 1}
REASONS = list(WEIGHTS)
FIELDS = {
    "_id": 0,
    "cardId": 1,
    "customId": 1,
    "title": 1,
    "status": 1,
    "columnId": 1,
    "ownerUserId": 1,
    "isBlocked": 1,
    "blockReason": 1,
    "currentBlockTimeSeconds": 1,
    "deadline": 1,
    "firstStartTime": 1,
    "inCurrentPositionSince": 1,
}


def _cycle_p85(db: Database, board_id: int, filters: CardFilters, period: Period, now: datetime) -> dict[str, Any]:
    values = [
        (c["endTime"] - c["firstStartTime"]).total_seconds() / DAY
        for c in db.cards.find(completed_query(board_id, filters, period, now), {"firstStartTime": 1, "endTime": 1})
        if c.get("firstStartTime") and c["endTime"] >= c["firstStartTime"]
    ]
    return {
        "p85": round(percentile(values, 85), 2) if values else None,
        "count": len(values),
        "smallSample": 0 < len(values) < SMALL_SAMPLE,
    }


def build_attention(
    db: Database,
    board: dict[str, Any],
    filters: CardFilters,
    period: Period,
    wip_limit: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    board_id = board["boardId"]
    enrich = CardEnricher(db, board, now)
    # Os motivos são calculados aqui: filtros de estado, bloqueio, prazos e datas não se aplicam.
    base = replace(
        filters,
        state="active",
        status=[],
        open=False,
        blocked=None,
        overdue=False,
        due_soon=False,
        created_from=None,
        created_to=None,
        ended_from=None,
        ended_to=None,
    )
    reference = _cycle_p85(db, board_id, base, period, now)
    threshold = reference["p85"]
    soon = now + timedelta(days=DUE_SOON_DAYS)

    open_query = {"$and": [build_query(board_id, base, period.tz, now), {"status": {"$nin": CLOSED_STATUSES}}]}
    open_total = 0
    wip: Counter = Counter()
    items: list[dict[str, Any]] = []
    for c in db.cards.find(open_query, FIELDS):
        open_total += 1
        status, owner, deadline = c.get("status"), c.get("ownerUserId"), c.get("deadline")
        reasons: list[str] = []
        age, estimated = (None, False)
        if status == "in_progress":
            wip[owner] += 1
            age, estimated = aging_days(c, now)
        if c.get("isBlocked"):
            reasons.append("blocked")
        if deadline and deadline < now:
            reasons.append("overdue")
        if threshold is not None and age is not None and age > threshold:
            reasons.append("aging")
        if deadline and now <= deadline < soon:
            reasons.append("dueSoon")
        if owner is None and status in ("todo", "in_progress"):
            reasons.append("unassigned")
        if not reasons:
            continue
        seconds = c.get("currentBlockTimeSeconds")
        block = c.get("blockReason") or {}
        items.append(
            {
                "cardId": c["cardId"],
                "customId": c.get("customId"),
                "title": c.get("title"),
                "status": status,
                "statusLabel": STATUS_LABELS.get(status, status),
                "columnName": enrich.column_name(c.get("columnId")),
                "ownerUserId": owner,
                "ownerName": enrich.user(owner),
                "reasons": reasons,
                "score": sum(WEIGHTS[r] for r in reasons),
                "blockedDays": round(seconds / DAY, 2) if c.get("isBlocked") and seconds is not None else None,
                "blockReason": block.get("label") if c.get("isBlocked") else None,
                "ageDays": None if age is None else round(age, 2),
                "ageEstimated": estimated,
                "deadline": deadline,
                "daysToDeadline": round((deadline - now).total_seconds() / DAY, 1) if deadline else None,
            }
        )
    items.sort(key=lambda i: (-i["score"], -(i["ageDays"] or 0), i["cardId"]))

    people = sorted(
        (
            {"userId": user_id, "name": enrich.user(user_id) or "Sem responsável", "inProgress": n}
            for user_id, n in wip.items()
            if user_id is not None and n > wip_limit
        ),
        key=lambda p: (-p["inProgress"], p["name"].lower()),
    )
    quality = build_quality(db, board, base, period, "month", now)

    return {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat()},
        "dueSoonDays": DUE_SOON_DAYS,
        "wipLimit": wip_limit,
        "agingReference": reference,
        "openTotal": open_total,
        "summary": {
            **{r: sum(1 for i in items if r in i["reasons"]) for r in REASONS},
            "wipOverLimit": len(people),
            "reopenedCards": quality["reopenedCards"],
        },
        "reopensAvailable": quality["available"],
        "total": len(items),
        "items": items[:MAX_ITEMS],
        "truncated": len(items) > MAX_ITEMS,
        "people": people,
    }
