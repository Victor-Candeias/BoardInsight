from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.api.v1.common import board_or_404, is_stale
from app.api.rate_limit import rate_limit
from app.repositories.jobs import JobRepository
from app.repositories.locks import LockRepository
from app.services.sync import lock_name

router = APIRouter(tags=["sync"])


def sync_status(db: DB, settings: AppSettings, board: dict[str, Any]) -> dict[str, Any]:
    board_id = board["boardId"]
    job = JobRepository(db).latest_for("sync_board", {"boardId": board_id})
    return {
        "boardId": board_id,
        "lastSyncAt": board.get("lastSyncAt"),
        "lastSuccessfulSyncAt": board.get("lastSuccessfulSyncAt"),
        "lastSyncStatus": board.get("lastSyncStatus"),
        "lastSyncError": board.get("lastSyncError"),
        "stale": is_stale(board, settings),
        "staleAfterMinutes": settings.stale_after_minutes,
        "running": LockRepository(db).is_locked(lock_name(board_id)),
        "latestJob": job,
    }


@router.post("/boards/{board_id}/sync", status_code=status.HTTP_202_ACCEPTED, dependencies=[rate_limit("sync")])
def enqueue_sync(board_id: int, db: DB, settings: AppSettings, response: Response) -> dict[str, Any]:
    board_or_404(db, board_id)
    settings.require_api_key()
    job, created = JobRepository(db).enqueue("sync_board", {"boardId": board_id})
    if not created:
        response.status_code = status.HTTP_200_OK
    return {"job": job, "created": created}


@router.get("/boards/{board_id}/sync-status")
def get_sync_status(board_id: int, db: DB, settings: AppSettings) -> dict[str, Any]:
    return sync_status(db, settings, board_or_404(db, board_id))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: DB) -> dict[str, Any]:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "job inexistente ou expirado")
    return job
