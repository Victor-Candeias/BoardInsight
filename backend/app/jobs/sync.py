"""Sincronização agendada (`businessmap-sync.service`, disparado pelo timer de 30 min).

Sincroniza todos os boards ativos, aplica a retenção e enfileira os relatórios agendados por sprint. Uso: python -m app.jobs.sync [--board ID]
Sai com código 1 se algum board falhar (visível em `systemctl status` / journald).
"""

import argparse
import asyncio
import logging

from app.core.config import ConfigurationError, get_settings
from app.core.database import get_database
from app.core.indexes import ensure_indexes
from app.core.logging import configure_logging
from app.services.retention import run_retention
from app.services.scheduled_reports import run_scheduled_reports
from app.services.sync import SyncService

logger = logging.getLogger("app.jobs.sync")


async def run(board_ids: list[int] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings)
    try:
        settings.require_api_key()
    except ConfigurationError as exc:
        logger.error("sync agendada não executada: %s", exc)
        return 2
    db = get_database()
    ensure_indexes(db, settings)
    service = SyncService(db, settings)
    ids = board_ids or service.boards.enabled_ids()
    if not ids:
        logger.warning("nenhum board ativo para sincronizar")
    results = [await service.sync_board(board_id, trigger="timer") for board_id in ids]
    run_retention(db, settings)
    try:
        run_scheduled_reports(db, settings)
    except Exception:
        logger.exception("falha nos relatórios agendados")
    failed = [r.board_id for r in results if r.status == "error"]
    logger.info("sync agendada terminada", extra={"boards": ids, "failed": failed})
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronização agendada BoardInsight")
    parser.add_argument("--board", type=int, action="append", help="sincronizar apenas este board (repetível)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.board)))


if __name__ == "__main__":
    main()
