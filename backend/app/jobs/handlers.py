"""Handlers dos tipos de job executados pelo worker."""

from collections.abc import Awaitable, Callable
from typing import Any

from pymongo.database import Database

from app.core.config import Settings
from app.services.sync import ClientFactory, SyncService

Handler = Callable[[Database, Settings, dict[str, Any], str, "ClientFactory | None"], Awaitable[dict[str, Any]]]


class JobFailed(Exception):
    def __init__(self, code: str, message: str, result: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.result = result


async def sync_board(
    db: Database, settings: Settings, payload: dict[str, Any], job_id: str, client_factory: ClientFactory | None = None
) -> dict[str, Any]:
    result = await SyncService(db, settings, client_factory).sync_board(int(payload["boardId"]), trigger="manual", job_id=job_id)
    data = {"boardId": result.board_id, "status": result.status, "runId": result.run_id, "stats": result.stats}
    if result.status != "success":
        error = result.error or {}
        raise JobFailed(error.get("code", "sync_failed"), error.get("message", "sincronização falhou"), data)
    return data


HANDLERS: dict[str, Handler] = {"sync_board": sync_board}
