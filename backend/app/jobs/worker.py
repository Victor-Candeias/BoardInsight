"""Worker de jobs (`businessmap-worker.service`): consome a coleção `jobs` do MongoDB.

Uso: python -m app.jobs.worker [--once]
"""

import argparse
import asyncio
import logging
import os
import signal
import socket
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from pymongo.database import Database

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.core.indexes import ensure_indexes
from app.core.logging import configure_logging
from app.jobs.handlers import HANDLERS, Handler, JobFailed
from app.repositories.jobs import JobRepository
from app.services.sync import ClientFactory

logger = logging.getLogger("app.jobs.worker")


class Worker:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        *,
        handlers: dict[str, Handler] | None = None,
        client_factory: ClientFactory | None = None,
    ):
        self.db = db
        self.settings = settings
        self.jobs = JobRepository(db)
        self.handlers = handlers if handlers is not None else HANDLERS
        self.client_factory = client_factory
        self.name = f"{socket.gethostname()}:{os.getpid()}"
        self._stop = asyncio.Event()

    @property
    def retention(self) -> timedelta:
        return timedelta(days=self.settings.job_retention_days)

    def stop(self) -> None:
        self._stop.set()

    async def run_one(self) -> dict[str, Any] | None:
        """Processa um job pendente, se existir. Devolve o job processado."""
        self.jobs.fail_stale(timedelta(minutes=self.settings.job_timeout_minutes), self.retention)
        job = self.jobs.claim(self.name)
        if job is None:
            return None
        log = {"job_id": job["id"], "job_type": job["type"]}
        handler = self.handlers.get(job["type"])
        if handler is None:
            self.jobs.finish(job["id"], "error", error={"code": "unknown_job_type", "message": job["type"]}, retention=self.retention)
            logger.error("tipo de job desconhecido", extra=log)
            return job
        logger.info("job iniciado", extra=log)
        try:
            result = await handler(self.db, self.settings, job["payload"], job["id"], self.client_factory)
        except JobFailed as exc:
            self.jobs.finish(job["id"], "error", result=exc.result, error={"code": exc.code, "message": exc.message}, retention=self.retention)
            logger.warning("job falhou", extra={**log, "error_code": exc.code})
        except Exception as exc:
            self.jobs.finish(job["id"], "error", error={"code": "internal_error", "message": type(exc).__name__}, retention=self.retention)
            logger.exception("job falhou com erro inesperado", extra=log)
        else:
            self.jobs.finish(job["id"], "done", result=result, retention=self.retention)
            logger.info("job concluído", extra=log)
        return job

    async def run_forever(self) -> None:
        logger.info("worker iniciado", extra={"worker": self.name})
        while not self._stop.is_set():
            processed = await self.run_one()
            if processed is None:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.settings.worker_poll_seconds)
                except TimeoutError:
                    pass
        logger.info("worker terminado", extra={"worker": self.name})


def install_stop_handlers(loop: asyncio.AbstractEventLoop, stop: Callable[[], None]) -> None:
    """SIGTERM/SIGINT param o worker. No Windows o loop não suporta `add_signal_handler` (o WinSW
    pára o serviço com Ctrl+C); usa-se `signal.signal`, que corre na thread principal."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop))


async def _main(once: bool) -> int:
    settings = get_settings()
    configure_logging(settings)
    db = get_database()
    ensure_indexes(db, settings)
    worker = Worker(db, settings)
    if once:
        while await worker.run_one():
            pass
        return 0
    install_stop_handlers(asyncio.get_running_loop(), worker.stop)
    await worker.run_forever()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de jobs BoardInsight")
    parser.add_argument("--once", action="store_true", help="processa os jobs pendentes e termina")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(args.once)))


if __name__ == "__main__":
    main()
