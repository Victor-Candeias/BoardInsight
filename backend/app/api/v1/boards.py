from typing import Any

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import DB, AppSettings, BmClientFactory
from app.api.errors import ApiError
from app.api.v1.common import board_or_404, is_stale
from app.repositories.boards import BoardRepository
from app.repositories.jobs import JobRepository
from app.repositories.sync_runs import SyncRunRepository
from app.services.boards import BOARD_DATA_COLLECTIONS, column_mapping, fetch_board_metadata, test_connection

router = APIRouter(prefix="/boards", tags=["boards"])

SUMMARY_FIELDS = ("boardId", "name", "workspaceId", "enabled", "isArchived", "lastSyncAt", "lastSuccessfulSyncAt", "lastSyncStatus", "cardCount", "createdAt")


class BoardCreate(BaseModel):
    boardId: int = Field(gt=0)


class BoardUpdate(BaseModel):
    enabled: bool | None = None


def summary(board: dict[str, Any], settings) -> dict[str, Any]:
    return {**{k: board.get(k) for k in SUMMARY_FIELDS}, "stale": is_stale(board, settings)}


def detail(board: dict[str, Any], settings) -> dict[str, Any]:
    structure = board.get("structure") or {}
    return {
        **summary(board, settings),
        "lastSyncError": board.get("lastSyncError"),
        "workflows": structure.get("workflows", []),
        "lanes": structure.get("lanes", []),
        "columns": column_mapping(board),
        "cardTypes": board.get("cardTypes", []),
        "metadataWarnings": board.get("metadataWarnings", []),
        "sprints": board.get("sprints"),
    }


@router.get("")
def list_boards(db: DB, settings: AppSettings, search: str | None = Query(None, max_length=100)) -> list[dict[str, Any]]:
    return [summary(b, settings) for b in BoardRepository(db).find_all(search)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_board(body: BoardCreate, db: DB, settings: AppSettings, client_factory: BmClientFactory) -> dict[str, Any]:
    repo = BoardRepository(db)
    if repo.get(body.boardId) is not None:
        raise ApiError(409, "board_exists", f"o board {body.boardId} já está configurado")
    settings.require_api_key()
    async with client_factory() as client:
        metadata = await fetch_board_metadata(client, body.boardId)
    board = repo.upsert_metadata(body.boardId, metadata)
    JobRepository(db).enqueue("sync_board", {"boardId": body.boardId})
    return detail(board, settings)


@router.get("/{board_id}")
def get_board(board_id: int, db: DB, settings: AppSettings) -> dict[str, Any]:
    return detail(board_or_404(db, board_id), settings)


@router.patch("/{board_id}")
def update_board(board_id: int, body: BoardUpdate, db: DB, settings: AppSettings) -> dict[str, Any]:
    board_or_404(db, board_id)
    changes = body.model_dump(exclude_none=True)
    board = BoardRepository(db).update(board_id, changes) if changes else board_or_404(db, board_id)
    return detail(board, settings)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: int, db: DB) -> Response:
    board_or_404(db, board_id)
    for name in BOARD_DATA_COLLECTIONS:
        db[name].delete_many({"boardId": board_id})
    db.jobs.delete_many({"payload.boardId": board_id, "status": "pending"})
    BoardRepository(db).delete(board_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{board_id}/test-connection")
async def board_test_connection(board_id: int, settings: AppSettings, client_factory: BmClientFactory) -> dict[str, Any]:
    """Pode ser usado antes de adicionar o board."""
    settings.require_api_key()
    async with client_factory() as client:
        return await test_connection(client, board_id)


@router.get("/{board_id}/sync-runs")
def sync_runs(board_id: int, db: DB, limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    board_or_404(db, board_id)
    return SyncRunRepository(db).recent(board_id, limit)
