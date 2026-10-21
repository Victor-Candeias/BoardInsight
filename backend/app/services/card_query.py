"""Filtros, ordenação e enriquecimento de cartões — partilhados por API de cartões, dashboards e exportações."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pymongo.database import Database

from app.models.cards import STATUS_LABELS
from app.repositories.base import utcnow
from app.repositories.users import UserCacheRepository

DUE_SOON_DAYS = 7
CLOSED_STATUSES = ["done", "archived", "discarded"]
SORT_FIELDS = {
    "cardId": "cardId",
    "customId": "customId",
    "title": "title",
    "status": "status",
    "priority": "priority",
    "size": "size",
    "createdAt": "createdAt",
    "lastModified": "lastModified",
    "deadline": "deadline",
    "firstStartTime": "firstStartTime",
    "endTime": "endTime",
    "position": "position",
}
StateFilter = Literal["active", "archived", "all"]


@dataclass
class CardFilters:
    q: str | None = None
    state: StateFilter = "active"
    status: list[str] = field(default_factory=list)
    column_id: list[int] = field(default_factory=list)
    lane_id: list[int] = field(default_factory=list)
    owner_user_id: list[int] = field(default_factory=list)
    unassigned: bool = False
    type_id: list[int] = field(default_factory=list)
    priority: list[int] = field(default_factory=list)
    blocked: bool | None = None
    overdue: bool = False
    due_soon: bool = False
    created_from: date | None = None
    created_to: date | None = None
    ended_from: date | None = None
    ended_to: date | None = None
    include_missing: bool = False


def day_start(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz)


def date_range(start: date | None, end: date | None, tz: ZoneInfo) -> dict[str, datetime] | None:
    """Intervalo [start, end] em dias locais (inclusivo) convertido para limites UTC."""
    cond: dict[str, datetime] = {}
    if start:
        cond["$gte"] = day_start(start, tz)
    if end:
        cond["$lt"] = day_start(end + timedelta(days=1), tz)
    return cond or None


def build_query(board_id: int, f: CardFilters, tz: ZoneInfo, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    query: dict[str, Any] = {"boardId": board_id}
    and_: list[dict[str, Any]] = []
    if f.state != "all":
        query["state"] = f.state
    if not f.include_missing:
        query["missingSince"] = None
    if f.status:
        query["status"] = {"$in": f.status}
    if f.column_id:
        query["columnId"] = {"$in": f.column_id}
    if f.lane_id:
        query["laneId"] = {"$in": f.lane_id}
    owners: list[dict[str, Any]] = []
    if f.owner_user_id:
        owners.append({"ownerUserId": {"$in": f.owner_user_id}})
    if f.unassigned:
        owners.append({"ownerUserId": None})
    if owners:
        and_.append({"$or": owners})
    if f.type_id:
        query["typeId"] = {"$in": f.type_id}
    if f.priority:
        query["priority"] = {"$in": f.priority}
    if f.blocked is not None:
        query["isBlocked"] = f.blocked
    if f.overdue or f.due_soon:
        deadline: dict[str, Any] = {"$ne": None}
        if f.overdue and not f.due_soon:
            deadline["$lt"] = now
        elif f.due_soon and not f.overdue:
            deadline |= {"$gte": now, "$lt": now + timedelta(days=DUE_SOON_DAYS)}
        else:
            deadline["$lt"] = now + timedelta(days=DUE_SOON_DAYS)
        query["deadline"] = deadline
        and_.append({"status": {"$nin": CLOSED_STATUSES}})
    if created := date_range(f.created_from, f.created_to, tz):
        query["createdAt"] = created
    if ended := date_range(f.ended_from, f.ended_to, tz):
        query["endTime"] = ended
    if f.q and f.q.strip():
        text = f.q.strip()
        pattern = {"$regex": re.escape(text), "$options": "i"}
        alternatives: list[dict[str, Any]] = [{"title": pattern}, {"customId": pattern}]
        if text.isdigit():
            alternatives.append({"cardId": int(text)})
        and_.append({"$or": alternatives})
    if and_:
        query["$and"] = and_
    return query


def sort_spec(sort: str | None) -> list[tuple[str, int]]:
    """`-createdAt` → descendente. Campo desconhecido → ordenação por omissão."""
    if not sort:
        return [("lastModified", -1), ("cardId", -1)]
    direction = -1 if sort.startswith("-") else 1
    name = SORT_FIELDS.get(sort.lstrip("-"))
    if name is None:
        raise ValueError(sort)
    return [(name, direction), ("cardId", direction)]


class CardEnricher:
    """Acrescenta nomes (coluna, lane, workflow, tipo, responsável) a partir do board e da cache de utilizadores."""

    def __init__(self, db: Database, board: dict[str, Any], now: datetime | None = None):
        structure = board.get("structure") or {}
        self.columns = {c["columnId"]: c for c in structure.get("columns", [])}
        self.lanes = {lane["laneId"]: lane.get("name") for lane in structure.get("lanes", [])}
        self.workflows = {w["workflowId"]: w.get("name") for w in structure.get("workflows", [])}
        self.types = {t["typeId"]: t.get("name") for t in board.get("cardTypes", [])}
        self.users = UserCacheRepository(db).names(board["boardId"])
        self.now = now or utcnow()

    def user(self, user_id: int | None) -> str | None:
        if user_id is None:
            return None
        return self.users.get(user_id, f"Utilizador {user_id}")

    def column_name(self, column_id: int | None) -> str | None:
        column = self.columns.get(column_id)
        if column is None:
            return None
        parent = self.columns.get(column.get("parentColumnId"))
        return f"{parent.get('name')} › {column.get('name')}" if parent else column.get("name")

    def __call__(self, card: dict[str, Any]) -> dict[str, Any]:
        deadline = card.get("deadline")
        open_ = card.get("status") not in CLOSED_STATUSES
        return {
            **card,
            "statusLabel": STATUS_LABELS.get(card.get("status"), card.get("status")),
            "columnName": self.column_name(card.get("columnId")),
            "laneName": self.lanes.get(card.get("laneId")),
            "workflowName": self.workflows.get(card.get("workflowId")),
            "typeName": self.types.get(card.get("typeId")),
            "ownerName": self.user(card.get("ownerUserId")),
            "coOwnerNames": [self.user(u) for u in card.get("coOwnerIds") or []],
            "overdue": bool(open_ and deadline and deadline < self.now),
            "dueSoon": bool(open_ and deadline and self.now <= deadline < self.now + timedelta(days=DUE_SOON_DAYS)),
            "missing": card.get("missingSince") is not None,
        }
