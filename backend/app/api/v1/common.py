from datetime import timedelta
from typing import Any

from pymongo.database import Database

from app.api.errors import ApiError
from app.core.config import Settings
from app.repositories.base import utcnow
from app.repositories.boards import BoardRepository


def board_or_404(db: Database, board_id: int) -> dict[str, Any]:
    board = BoardRepository(db).get(board_id)
    if board is None:
        raise ApiError(404, "board_not_found", f"o board {board_id} não está configurado")
    return board


def is_stale(board: dict[str, Any], settings: Settings) -> bool:
    last_ok = board.get("lastSuccessfulSyncAt")
    return last_ok is None or utcnow() - last_ok > timedelta(minutes=settings.stale_after_minutes)
