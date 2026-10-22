from typing import Any

from fastapi import APIRouter

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.api.v1.common import board_or_404, is_stale
from app.api.v1.filters import Filters
from app.repositories.boards import BoardRepository
from app.services.sprints import SprintConfig, build_sprint, build_sprints

router = APIRouter(prefix="/boards/{board_id}/sprints", tags=["sprints"])


@router.get("")
def sprints(board_id: int, db: DB, settings: AppSettings, filters: Filters) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    return build_sprints(db, board, filters, settings.tz) | {"stale": is_stale(board, settings)}


@router.put("/config")
def update_config(board_id: int, body: SprintConfig, db: DB) -> dict[str, Any]:
    board_or_404(db, board_id)
    board = BoardRepository(db).update(board_id, {"sprints": body.to_document()})
    return board["sprints"]


@router.get("/{sprint_id}")
def sprint(board_id: int, sprint_id: str, db: DB, settings: AppSettings, filters: Filters) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    result = build_sprint(db, board, sprint_id, filters, settings.tz)
    if result is None:
        raise ApiError(404, "sprint_not_found", f"sprint {sprint_id} não encontrada")
    return result | {"stale": is_stale(board, settings)}
