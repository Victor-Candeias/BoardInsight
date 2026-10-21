"""Métricas de fluxo (E2): WIP, aging, lead/cycle time e percentis (ver metrics-definitions)."""

import math
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
from typing import Any

from pymongo.database import Database

from app.repositories.base import utcnow
from app.services.card_query import CardEnricher, CardFilters, aging_days, build_query
from app.services.delivery import completed_query
from app.services.periods import Granularity, Period, bucket_label, bucket_of, buckets

PERCENTILES = (50, 85, 95)
SMALL_SAMPLE = 5
MAX_POINTS = 2000
MAX_AGING_ITEMS = 300
DAY = 86400


def percentile(values: list[float], p: float) -> float:
    """Interpolação linear entre ordens (método por omissão do NumPy)."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p / 100
    lower, upper = math.floor(pos), math.ceil(pos)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def summarize(values: list[float], missing_reason: str) -> dict[str, Any]:
    if not values:
        return {"available": False, "reason": missing_reason, "count": 0}
    return {
        "available": True,
        "count": len(values),
        "smallSample": len(values) < SMALL_SAMPLE,
        **{f"p{p}": round(percentile(values, p), 2) for p in PERCENTILES},
        "mean": round(sum(values) / len(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def _days(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end or end < start:
        return None
    return (end - start).total_seconds() / DAY


def build_flow(
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

    # Lead/cycle time dos cartões concluídos no período.
    completed = list(
        db.cards.find(
            completed_query(board_id, filters, period, now),
            {"_id": 0, "cardId": 1, "customId": 1, "title": 1, "createdAt": 1, "firstStartTime": 1, "endTime": 1, "typeId": 1},
        )
    )
    points = []
    per_bucket: dict[Any, dict[str, list[float]]] = defaultdict(lambda: {"lead": [], "cycle": []})
    for c in completed:
        end = c["endTime"]  # fim = last_end_time ou first_end_time (normalização)
        lead, cycle = _days(c.get("createdAt"), end), _days(c.get("firstStartTime"), end)
        points.append(
            {
                "cardId": c["cardId"],
                "customId": c.get("customId"),
                "title": c.get("title"),
                "typeName": enrich.types.get(c.get("typeId")),
                "endTime": end,
                "leadDays": None if lead is None else round(lead, 2),
                "cycleDays": None if cycle is None else round(cycle, 2),
            }
        )
        b = bucket_of(c["endTime"], granularity, period.tz)
        if lead is not None:
            per_bucket[b]["lead"].append(lead)
        if cycle is not None:
            per_bucket[b]["cycle"].append(cycle)
    lead_values = [p["leadDays"] for p in points if p["leadDays"] is not None]
    cycle_values = [p["cycleDays"] for p in points if p["cycleDays"] is not None]
    no_done = "sem cartões concluídos no período"
    cycle_time = summarize(cycle_values, no_done if not points else "nenhum cartão concluído tem data de início")
    cycle_time["withoutStart"] = len(points) - len(cycle_values)

    trend = []
    for b in buckets(period, granularity):
        values = per_bucket.get(b, {"lead": [], "cycle": []})
        trend.append(
            {
                "bucket": b.isoformat(),
                "label": bucket_label(b, granularity),
                "count": max(len(values["lead"]), len(values["cycle"])),
                "cycleP50": round(percentile(values["cycle"], 50), 2) if values["cycle"] else None,
                "cycleP85": round(percentile(values["cycle"], 85), 2) if values["cycle"] else None,
                "leadP50": round(percentile(values["lead"], 50), 2) if values["lead"] else None,
            }
        )

    # WIP e aging: estado atual (filtros aplicados, só em curso).
    wip_filters = replace(filters, state="active", status=["in_progress"])
    wip_cards = list(db.cards.find(build_query(board_id, wip_filters, period.tz, now), {"_id": 0, "raw": 0, "transitions": 0}))
    threshold = cycle_time.get("p85")
    aging = []
    for c in wip_cards:
        age, estimated = aging_days(c, now)
        aging.append(
            {
                "cardId": c["cardId"],
                "customId": c.get("customId"),
                "title": c.get("title"),
                "columnName": enrich.column_name(c.get("columnId")),
                "ownerName": enrich.user(c.get("ownerUserId")),
                "isBlocked": bool(c.get("isBlocked")),
                "ageDays": None if age is None else round(age, 2),
                "estimated": estimated,
                "aboveP85": bool(threshold is not None and age is not None and age > threshold),
            }
        )
    aging.sort(key=lambda a: (a["ageDays"] is None, -(a["ageDays"] or 0)))
    ages = [a["ageDays"] for a in aging if a["ageDays"] is not None]

    def dist(key: str, label) -> list[dict[str, Any]]:
        counts = Counter(c.get(key) for c in wip_cards)
        return [{"key": k, "label": label(k), "count": n} for k, n in counts.most_common()]

    column_order = {c["columnId"]: i for i, c in enumerate((board.get("structure") or {}).get("columns", []))}
    by_column = sorted(dist("columnId", lambda k: enrich.column_name(k) or "—"), key=lambda d: column_order.get(d["key"], 999))

    return {
        "boardId": board_id,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": granularity},
        "wip": {
            "total": len(wip_cards),
            "blocked": sum(1 for c in wip_cards if c.get("isBlocked")),
            "byColumn": by_column,
            "byLane": dist("laneId", lambda k: enrich.lanes.get(k) or "—"),
            "byOwner": dist("ownerUserId", lambda k: enrich.user(k) or "Sem responsável"),
        },
        "aging": {
            **summarize(ages, "sem cartões em curso"),
            "threshold": threshold,
            "aboveThreshold": sum(1 for a in aging if a["aboveP85"]),
            "estimatedCount": sum(1 for a in aging if a["estimated"]),
            "items": aging[:MAX_AGING_ITEMS],
        },
        "leadTime": summarize(lead_values, no_done),
        "cycleTime": cycle_time,
        "trend": trend,
        "points": sorted(points, key=lambda p: p["endTime"])[-MAX_POINTS:],
    }
