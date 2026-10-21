"""Throughput e prazos (README §5.3; definições em metrics-definitions)."""

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pymongo.database import Database

from app.repositories.base import utcnow
from app.services.card_query import CLOSED_STATUSES, DUE_SOON_DAYS, CardEnricher, CardFilters, build_query
from app.services.periods import Granularity, Period, bucket_label, bucket_of, buckets, next_bucket

DEADLINE_LIST_LIMIT = 500
CARD_PROJECTION = {"_id": 0, "raw": 0, "transitions": 0}


def completed_query(board_id: int, filters: CardFilters, period: Period, now: datetime) -> dict[str, Any]:
    """Cartões com data de fim no período (inclui arquivados; descartados não contam como entregas)."""
    f = replace(filters, state="all", status=[], created_from=None, created_to=None, ended_from=None, ended_to=None)
    query = build_query(board_id, f, period.tz, now)
    return {"$and": [query, {"endTime": {"$gte": period.start_utc, "$lt": period.end_utc}}, {"status": {"$ne": "discarded"}}]}


def build_throughput(
    db: Database,
    board: dict[str, Any],
    filters: CardFilters,
    period: Period,
    granularity: Granularity,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    enrich = CardEnricher(db, board, now)
    done = list(db.cards.find(completed_query(board["boardId"], filters, period, now), {"endTime": 1, "size": 1, "typeId": 1}))
    count: Counter = Counter()
    size: Counter = Counter()
    for c in done:
        b = bucket_of(c["endTime"], granularity, period.tz)
        count[b] += 1
        size[b] += c.get("size") or 0
    series = []
    for b in buckets(period, granularity):
        end = next_bucket(b, granularity) - timedelta(days=1)
        series.append(
            {
                "bucket": b.isoformat(),
                "label": bucket_label(b, granularity),
                "count": count[b],
                "size": size[b],
                # intervalo cortado pelo início/fim do período: não comparável com os restantes
                "partial": b < period.start or end > period.end,
            }
        )
    full = [s for s in series if not s["partial"]] or series
    types = Counter(c.get("typeId") for c in done)
    return {
        "boardId": board["boardId"],
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": granularity},
        "total": len(done),
        "totalSize": sum(size.values()),
        "averagePerBucket": round(sum(s["count"] for s in full) / len(full), 2) if full else 0,
        "series": series,
        "byType": [
            {"key": k, "label": enrich.types.get(k) or "Sem tipo", "count": n} for k, n in types.most_common()
        ],
    }


def build_deadlines(
    db: Database, board: dict[str, Any], filters: CardFilters, tz: ZoneInfo, now: datetime | None = None
) -> dict[str, Any]:
    now = now or utcnow()
    board_id = board["boardId"]
    enrich = CardEnricher(db, board, now)

    def cards(*, overdue: bool = False, due_soon: bool = False) -> tuple[list[dict[str, Any]], int, Counter]:
        query = build_query(board_id, replace(filters, overdue=overdue, due_soon=due_soon), tz, now)
        owners = Counter(c.get("ownerUserId") for c in db.cards.find(query, {"ownerUserId": 1}))
        total = sum(owners.values())
        items = [enrich(c) for c in db.cards.find(query, CARD_PROJECTION).sort([("deadline", 1), ("cardId", 1)]).limit(DEADLINE_LIST_LIMIT)]
        for item in items:
            item["daysToDeadline"] = round((item["deadline"] - now).total_seconds() / 86400, 1)
        return items, total, owners

    overdue, overdue_total, owners = cards(overdue=True)
    due_soon, due_soon_total, _ = cards(due_soon=True)
    open_query = build_query(board_id, replace(filters, overdue=False, due_soon=False), tz, now)
    open_query = {"$and": [open_query, {"status": {"$nin": CLOSED_STATUSES}}]}
    open_total = db.cards.count_documents(open_query)
    without = db.cards.count_documents({"$and": [open_query, {"deadline": None}]})
    return {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "dueSoonDays": DUE_SOON_DAYS,
        "openTotal": open_total,
        "withoutDeadline": without,
        "overdue": {"total": overdue_total, "items": overdue, "truncated": overdue_total > len(overdue)},
        "dueSoon": {"total": due_soon_total, "items": due_soon, "truncated": due_soon_total > len(due_soon)},
        "overdueByOwner": [
            {"key": k, "label": enrich.user(k) if k is not None else "Sem responsável", "count": n} for k, n in owners.most_common()
        ],
    }
