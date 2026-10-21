from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.repositories.base import utcnow
from app.repositories.boards import BoardRepository
from app.repositories.jobs import JobRepository
from app.repositories.locks import LockRepository
from app.services.sync import lock_name

router = APIRouter(tags=["sync"])


def _board_or_404(db: DB, board_id: int) -> dict[str, Any]:
    board = BoardRepository(db).get(board_id)
    if board is None:
        raise ApiError(404, "board_not_found", f"o board {board_id} não está configurado")
    return board


def sync_status(db: DB, settings: AppSettings, board: dict[str, Any]) -> dict[str, Any]:
    board_id = board["boardId"]
    last_ok = board.get("lastSuccessfulSyncAt")
    stale_after = timedelta(minutes=settings.stale_after_minutes)
    job = JobRepository(db).latest_for("sync_board", {"boardId": board_id})
    return {
        "boardId": board_id,
        "lastSyncAt": board.get("lastSyncAt"),
        "lastSuccessfulSyncAt": last_ok,
        "lastSyncStatus": board.get("lastSyncStatus"),
        "lastSyncError": board.get("lastSyncError"),
        "stale": last_ok is None or utcnow() - last_ok > stale_after,
        "staleAfterMinutes": settings.stale_after_minutes,
        "running": LockRepository(db).is_locked(lock_name(board_id)),
        "latestJob": job,
    }


@router.post("/boards/{board_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def enqueue_sync(board_id: int, db: DB, settings: AppSettings, response: Response) -> dict[str, Any]:
    _board_or_404(db, board_id)
    settings.require_api_key()
    job, created = JobRepository(db).enqueue("sync_board", {"boardId": board_id})
    if not created:
        response.status_code = status.HTTP_200_OK
    return {"job": job, "created": created}


@router.get("/boards/{board_id}/sync-status")
def get_sync_status(board_id: int, db: DB, settings: AppSettings) -> dict[str, Any]:
    return sync_status(db, settings, _board_or_404(db, board_id))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: DB) -> dict[str, Any]:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "job inexistente ou expirado")
    return job
