"""Modelo interno dos cartões (collection `cards`) e normalização a partir do DTO Businessmap."""

from datetime import datetime
from typing import Any, Literal

from app.models.businessmap import BmCard

CardState = Literal["active", "archived", "discarded"]
CardStatus = Literal["backlog", "todo", "in_progress", "done", "archived", "discarded", "unknown"]

SECTION_STATUS: dict[int, CardStatus] = {1: "backlog", 2: "todo", 3: "in_progress", 4: "done", 5: "done"}
STATUS_LABELS = {
    "backlog": "Backlog",
    "todo": "A fazer",
    "in_progress": "Em curso",
    "done": "Concluído",
    "archived": "Arquivado",
    "discarded": "Descartado",
    "unknown": "Desconhecido",
}
ACTIVE_STATUSES = ("todo", "in_progress")
PRIORITY_LABELS = {1: "Crítica", 2: "Alta", 3: "Média", 4: "Baixa"}

# Campos usados para detetar alterações entre syncs (eventos observados, E1).
TRACKED_FIELDS = ("columnId", "laneId", "section", "status", "isBlocked", "ownerUserId", "state")


def priority_level(priority: int | None) -> int:
    """Nível normalizado 1–4 (a API trata `null` como Média e >4 como Baixa)."""
    if priority is None:
        return 3
    return max(1, min(priority, 4))


def derive_status(state: CardState, section: int | None, end_time: datetime | None) -> CardStatus:
    if state == "discarded":
        return "discarded"
    if state == "archived":
        return "done" if end_time else "archived"
    return SECTION_STATUS.get(section or 0, "unknown")


def card_url(base_url: str, board_id: int, card_id: int) -> str:
    return f"{base_url}/ctrl_board/{board_id}/cards/{card_id}/details/"


def normalize_card(
    card: BmCard,
    *,
    state: CardState,
    columns: dict[int, dict[str, Any]],
    base_url: str,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    column = columns.get(card.column_id or -1) or columns.get(card.last_column_id or -1) or {}
    section = card.section if card.section is not None else column.get("section")
    end_time = card.last_end_time or card.first_end_time
    status = derive_status(state, section, end_time)
    level = priority_level(card.priority)
    doc: dict[str, Any] = {
        "boardId": card.board_id,
        "cardId": card.card_id,
        "customId": card.custom_id,
        "title": card.title,
        "url": card_url(base_url, card.board_id, card.card_id),
        "state": state,
        "status": status,
        "workflowId": card.workflow_id,
        "columnId": card.column_id if card.column_id is not None else card.last_column_id,
        "laneId": card.lane_id if card.lane_id is not None else card.last_lane_id,
        "section": section,
        "position": card.position,
        "ownerUserId": card.owner_user_id,
        "coOwnerIds": card.co_owner_ids,
        "typeId": card.type_id,
        "size": card.size,
        "priority": level,
        "priorityLabel": PRIORITY_LABELS[level],
        "color": card.color,
        "tagIds": card.tag_ids,
        "deadline": card.deadline,
        "createdAt": card.created_at,
        "lastModified": card.last_modified,
        "inCurrentPositionSince": card.in_current_position_since,
        "firstRequestTime": card.first_request_time,
        "firstStartTime": card.first_start_time,
        "lastStartTime": card.last_start_time,
        "firstEndTime": card.first_end_time,
        "lastEndTime": card.last_end_time,
        "endTime": end_time if status == "done" else None,
        "archivedAt": card.archived_at,
        "discardedAt": card.discarded_at,
        "isBlocked": card.is_blocked,
        "blockReason": (
            {"reasonId": card.block_reason.reason_id, "label": card.block_reason.label, "comment": card.block_reason.comment}
            if card.is_blocked and card.block_reason
            else None
        ),
        "currentBlockTimeSeconds": card.current_block_time if card.is_blocked else None,
        "loggedTimeSeconds": card.current_logged_time,
        "transitions": [t.model_dump(exclude_none=True) for t in card.transitions],
    }
    if raw is not None:
        doc["raw"] = raw
    return doc
