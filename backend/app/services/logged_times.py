"""Tempo registado (D8): recolha de `GET /loggedTime` no sync e relatório da página Horas.

A API não filtra por board: pede-se por intervalo de datas e ficam só as entradas cujo cartão, coluna ou lane
pertencem ao board. As entradas da janela recente são reconciliadas (as que deixaram de vir são removidas).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from pymongo.database import Database

from app.integrations.businessmap import BusinessmapClient
from app.models.businessmap import BmLoggedTime
from app.services.card_query import CardEnricher
from app.services.periods import Granularity, Period, bucket_label, bucket_start, buckets

MAX_ENTRIES = 2000
DISCLAIMER = (
    "Horas registadas no Businessmap pelas pessoas. Servem para acompanhar o esforço registado; "
    "não são uma avaliação de desempenho individual nem incluem trabalho que não foi registado."
)


def day_value(day: date) -> datetime:
    """O dia do trabalho guarda-se como meia-noite UTC (dia de calendário, sem conversão de fuso)."""
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


@dataclass
class LoggedTimeFetch:
    window_start: date
    entries: dict[int, dict[str, Any]] = field(default_factory=dict)
    window_ids: set[int] = field(default_factory=set)
    pages: int = 0
    invalid: int = 0
    skipped_other_boards: int = 0


def _doc(board_id: int, entry: BmLoggedTime) -> dict[str, Any]:
    return {
        "boardId": board_id,
        "loggedTimeId": entry.logged_time_id,
        "cardId": entry.card_id,
        "parentCardId": entry.parent_card_id,
        "subtaskId": entry.subtask_id,
        "userId": entry.user_id,
        "categoryId": entry.category_id,
        "laneId": entry.lane_id,
        "columnId": entry.column_id,
        "date": day_value(entry.date) if entry.date else None,
        "seconds": max(entry.time, 0),
        "comment": entry.comment,
        "loggedAt": entry.logged_at,
    }


async def fetch_logged_times(
    client: BusinessmapClient,
    *,
    board_id: int,
    card_ids: set[int],
    column_ids: set[int],
    lane_ids: set[int],
    today: date,
    window_days: int,
    last_synced_at: datetime | None,
) -> LoggedTimeFetch:
    """Lê tudo antes de escrever (como os cartões). Lança `BusinessmapError` em falha."""
    result = LoggedTimeFetch(window_start=today - timedelta(days=window_days))

    def belongs(entry: BmLoggedTime) -> bool:
        return entry.card_id in card_ids or entry.column_id in column_ids or entry.lane_id in lane_ids

    async def read(in_window: bool, **filters: Any) -> None:
        async for page in client.iter_logged_times(include_logged_time_for_subtasks=1, **filters):
            result.pages += 1
            for raw in page:
                try:
                    entry = BmLoggedTime.model_validate(raw)
                except ValidationError:
                    result.invalid += 1
                    continue
                if not belongs(entry):
                    result.skipped_other_boards += 1
                    continue
                result.entries[entry.logged_time_id] = _doc(board_id, entry)
                if in_window:
                    result.window_ids.add(entry.logged_time_id)

    await read(True, from_date=result.window_start.isoformat())
    if last_synced_at is not None:
        # Registos novos com datas anteriores à janela (ex.: horas de há dois meses registadas hoje).
        since = (last_synced_at - timedelta(days=1)).date()
        if since < today:
            await read(False, logged_from_date=since.isoformat())
    return result


def store_logged_times(db: Database, board_id: int, fetched: LoggedTimeFetch, now: datetime) -> dict[str, int]:
    for lid, doc in fetched.entries.items():
        db.logged_times.update_one({"boardId": board_id, "loggedTimeId": lid}, {"$set": {**doc, "seenAt": now}}, upsert=True)
    # Na janela pedida por data, o que não veio foi apagado ou mudou de dia/board no Businessmap.
    removed = db.logged_times.delete_many(
        {"boardId": board_id, "date": {"$gte": day_value(fetched.window_start)}, "loggedTimeId": {"$nin": sorted(fetched.window_ids)}}
    ).deleted_count
    return {"loggedTimeEntries": len(fetched.entries), "loggedTimeRemoved": removed, "loggedTimePages": fetched.pages}


def build_hours(
    db: Database,
    board: dict[str, Any],
    period: Period,
    granularity: Granularity,
    *,
    user_id: int | None = None,
    include_subtasks: bool = True,
) -> dict[str, Any]:
    board_id = board["boardId"]
    enrich = CardEnricher(db, board)
    query: dict[str, Any] = {"boardId": board_id, "date": {"$gte": day_value(period.start), "$lte": day_value(period.end)}}
    if user_id is not None:
        query["userId"] = user_id
    if not include_subtasks:
        query["subtaskId"] = None

    bucket_list = buckets(period, granularity)
    index = {b: i for i, b in enumerate(bucket_list)}
    total = 0
    days: set[date] = set()
    cards: set[int] = set()
    per_user: dict[int | None, dict[str, Any]] = defaultdict(
        lambda: {"seconds": 0, "entries": 0, "cards": set(), "days": set(), "series": [0] * len(bucket_list)}
    )
    entries: list[dict[str, Any]] = []
    for e in db.logged_times.find(query, {"_id": 0}).sort([("date", -1), ("loggedTimeId", -1)]):
        day = e["date"].date()
        seconds = e.get("seconds") or 0
        row = per_user[e.get("userId")]
        row["seconds"] += seconds
        row["entries"] += 1
        row["days"].add(day)
        row["series"][index[bucket_start(day, granularity)]] += seconds
        if e.get("cardId") is not None:
            row["cards"].add(e["cardId"])
            cards.add(e["cardId"])
        total += seconds
        days.add(day)
        entries.append(e)

    card_info = {
        c["cardId"]: c for c in db.cards.find({"boardId": board_id, "cardId": {"$in": sorted(cards)}}, {"_id": 0, "cardId": 1, "customId": 1, "title": 1, "url": 1})
    }

    def name(uid: int | None) -> str:
        return enrich.user(uid) if uid is not None else "Sem utilizador"

    by_user = sorted(
        (
            {
                "userId": uid,
                "name": name(uid),
                "seconds": row["seconds"],
                "entries": row["entries"],
                "cards": len(row["cards"]),
                "days": len(row["days"]),
                "avgSecondsPerDay": round(row["seconds"] / len(row["days"])) if row["days"] else 0,
                "series": row["series"],
            }
            for uid, row in per_user.items()
        ),
        key=lambda r: (-r["seconds"], r["name"].lower()),
    )
    users = sorted(
        ({"userId": uid, "name": name(uid)} for uid in db.logged_times.distinct("userId", {"boardId": board_id}) if uid is not None),
        key=lambda u: u["name"].lower(),
    )
    if user_id is not None and all(u["userId"] != user_id for u in users):
        users.append({"userId": user_id, "name": name(user_id)})

    def entry_out(e: dict[str, Any]) -> dict[str, Any]:
        card = card_info.get(e.get("cardId")) or {}
        return {
            "loggedTimeId": e["loggedTimeId"],
            "date": e["date"].date().isoformat(),
            "userId": e.get("userId"),
            "userName": name(e.get("userId")),
            "cardId": e.get("cardId"),
            "customId": card.get("customId"),
            "title": card.get("title"),
            "url": card.get("url"),
            "subtask": e.get("subtaskId") is not None,
            "seconds": e.get("seconds") or 0,
            "comment": e.get("comment"),
        }

    error = board.get("loggedTimeError")
    return {
        "boardId": board_id,
        "dataAsOf": board.get("loggedTimeSyncedAt") or board.get("lastSuccessfulSyncAt"),
        "available": board.get("loggedTimeSyncedAt") is not None,
        "warning": f"Última recolha do tempo registado falhou: {error.get('message')}" if error else None,
        "period": {"from": period.start.isoformat(), "to": period.end.isoformat(), "granularity": granularity},
        "buckets": [{"bucket": b.isoformat(), "label": bucket_label(b, granularity)} for b in bucket_list],
        "userId": user_id,
        "includeSubtasks": include_subtasks,
        "users": users,
        "totalSeconds": total,
        "entryCount": len(entries),
        "cardCount": len(cards),
        "peopleCount": len(per_user),
        "dayCount": len(days),
        "byUser": by_user,
        "entries": [entry_out(e) for e in entries[:MAX_ENTRIES]],
        "truncated": len(entries) > MAX_ENTRIES,
        "disclaimer": DISCLAIMER,
    }
