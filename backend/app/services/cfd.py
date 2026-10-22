"""Cumulative Flow Diagram (E3): último snapshot de cada dia, por estado ou coluna."""

from datetime import datetime
from typing import Any, Literal

from pymongo.database import Database

from app.repositories.base import utcnow
from app.models.cards import STATUS_LABELS
from app.services.card_query import CardEnricher, CardFilters, build_query
from app.services.history import SNAPSHOT_STATUSES, history_since
from app.services.periods import Period, bucket_of

CfdGroup = Literal["status", "column"]


def stable_filter_ids(db: Database, board_id: int, filters: CardFilters, period: Period, now: datetime) -> set[int] | None:
    """Ids dos cartões que cumprem os filtros (atributos atuais); None = sem filtros."""
    if not (filters.q or filters.owner_user_id or filters.unassigned or filters.type_id or filters.priority):
        return None
    f = CardFilters(
        q=filters.q,
        state="all",
        owner_user_id=filters.owner_user_id,
        unassigned=filters.unassigned,
        type_id=filters.type_id,
        priority=filters.priority,
        include_missing=True,
    )
    return set(db.cards.distinct("cardId", build_query(board_id, f, period.tz, now)))


def build_cfd(
    db: Database,
    board: dict[str, Any],
    filters: CardFilters,
    period: Period,
    group: CfdGroup,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utcnow()
    board_id = board["boardId"]
    allowed = stable_filter_ids(db, board_id, filters, period, now)

    last_per_day: dict[Any, dict[str, Any]] = {}
    cursor = db.board_snapshots.find(
        {"boardId": board_id, "capturedAt": {"$gte": period.start_utc, "$lt": period.end_utc}}, {"_id": 0}
    ).sort("capturedAt", 1)
    for snap in cursor:
        last_per_day[bucket_of(snap["capturedAt"], "day", period.tz)] = snap

    if group == "status":
        series = [{"key": s, "label": STATUS_LABELS[s]} for s in SNAPSHOT_STATUSES]

        def counts(snap: dict[str, Any]) -> dict[str, int]:
            ids = snap.get("cardIds") or {}
            if allowed is None:
                return {s: int((snap.get("byStatus") or {}).get(s, 0)) for s in SNAPSHOT_STATUSES}
            return {s: len(allowed.intersection(ids.get(s, []))) for s in SNAPSHOT_STATUSES}

    else:
        enrich = CardEnricher(db, board, now)
        order = [c["columnId"] for c in (board.get("structure") or {}).get("columns", [])]
        seen = {e["key"] for snap in last_per_day.values() for e in snap.get("byColumn", [])}
        keys = [k for k in order if k in seen] + sorted((k for k in seen if k not in order), key=lambda k: (k is None, k or 0))
        series = [{"key": str(k), "label": enrich.column_name(k) or ("Sem coluna" if k is None else f"Coluna {k}")} for k in keys]

        def counts(snap: dict[str, Any]) -> dict[str, int]:
            out = {str(k): 0 for k in keys}
            for e in snap.get("byColumn", []):
                n = e.get("count", 0) if allowed is None else len(allowed.intersection(e.get("cardIds", [])))
                out[str(e["key"])] = n
            return out

    days = [
        {"date": day.isoformat(), "capturedAt": snap["capturedAt"], "counts": counts(snap)}
        for day, snap in sorted(last_per_day.items())
    ]
    since = history_since(db, board_id)["snapshotsSince"]
    result: dict[str, Any] = {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": "day"},
        "group": group,
        "filtered": allowed is not None,
        "snapshotsSince": since,
        "available": bool(days),
        "series": series,
        "days": days,
    }
    if not days:
        result["reason"] = "recolha de histórico ainda não iniciada" if since is None else "sem snapshots no período"
    return result
