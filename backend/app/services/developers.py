"""Página Developers: distribuição de trabalho por responsável (uso pessoal do tech lead, não é avaliação)."""

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
from statistics import mean
from typing import Any

from pymongo.database import Database

from app.repositories.base import utcnow
from app.services.card_query import CLOSED_STATUSES, CardEnricher, CardFilters, aging_days, build_query
from app.services.delivery import completed_query
from app.services.periods import Granularity, Period, bucket_label, bucket_of, buckets

DISCLAIMER = (
    "Contagens de uso pessoal do tech lead para acompanhar a distribuição de trabalho. "
    "Não são uma avaliação de desempenho individual: tamanho, complexidade e trabalho fora do board não estão refletidos."
)
FIELDS = {"_id": 0, "ownerUserId": 1, "coOwnerIds": 1, "status": 1, "isBlocked": 1, "deadline": 1, "firstStartTime": 1, "inCurrentPositionSince": 1}


def _row() -> dict[str, Any]:
    return {"backlog": 0, "todo": 0, "inProgress": 0, "blocked": 0, "overdue": 0, "coOwnedOpen": 0, "completed": 0, "completedSize": 0, "aging": []}


def build_developers(
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
    # A página agrupa por pessoa: filtros de responsável, estado e prazos não se aplicam.
    base = replace(filters, owner_user_id=[], unassigned=False, state="active", status=[], overdue=False, due_soon=False)
    rows: dict[int | None, dict[str, Any]] = defaultdict(_row)

    open_query = {"$and": [build_query(board_id, base, period.tz, now), {"status": {"$nin": CLOSED_STATUSES}}]}
    for c in db.cards.find(open_query, FIELDS):
        row = rows[c.get("ownerUserId")]
        status = c.get("status")
        if status == "backlog":
            row["backlog"] += 1
        elif status == "todo":
            row["todo"] += 1
        elif status == "in_progress":
            row["inProgress"] += 1
            days, estimated = aging_days(c, now)
            if days is not None:
                row["aging"].append((days, estimated))
        row["blocked"] += bool(c.get("isBlocked"))
        row["overdue"] += bool(c.get("deadline") and c["deadline"] < now)
        for co in set(c.get("coOwnerIds") or []) - {c.get("ownerUserId")}:
            rows[co]["coOwnedOpen"] += 1

    series: dict[int | None, Counter] = defaultdict(Counter)
    for c in db.cards.find(completed_query(board_id, base, period, now), {"ownerUserId": 1, "endTime": 1, "size": 1}):
        owner = c.get("ownerUserId")
        rows[owner]["completed"] += 1
        rows[owner]["completedSize"] += c.get("size") or 0
        series[owner][bucket_of(c["endTime"], granularity, period.tz)] += 1

    bucket_list = buckets(period, granularity)
    developers = []
    for user_id, row in rows.items():
        aging = row.pop("aging")
        developers.append(
            {
                "userId": user_id,
                "name": enrich.user(user_id) if user_id is not None else "Sem responsável",
                **row,
                "open": row["backlog"] + row["todo"] + row["inProgress"],
                "avgAgingDays": round(mean(d for d, _ in aging), 1) if aging else None,
                "maxAgingDays": round(max(d for d, _ in aging), 1) if aging else None,
                "agingEstimated": any(e for _, e in aging),
                "completedSeries": [series[user_id][b] for b in bucket_list],
            }
        )
    developers.sort(key=lambda d: (d["userId"] is None, d["name"].lower()))
    return {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": granularity},
        "buckets": [{"bucket": b.isoformat(), "label": bucket_label(b, granularity)} for b in bucket_list],
        "developers": developers,
        "disclaimer": DISCLAIMER,
    }
