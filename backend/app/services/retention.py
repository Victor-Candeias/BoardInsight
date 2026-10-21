"""Limpeza periódica (README §13): payload bruto > RETENTION_RAW_DAYS e ficheiros de exportação expirados."""

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

from pymongo.database import Database

from app.core.config import Settings
from app.repositories.base import utcnow

logger = logging.getLogger(__name__)


def purge_raw_payloads(db: Database, settings: Settings) -> int:
    cutoff = utcnow() - timedelta(days=settings.retention_raw_days)
    result = db.cards.update_many({"raw": {"$exists": True}, "rawUpdatedAt": {"$lt": cutoff}}, {"$unset": {"raw": ""}})
    return result.modified_count


def purge_export_files(settings: Settings) -> int:
    root: Path = settings.export_dir
    if not root.is_dir():
        return 0
    cutoff = (utcnow() - timedelta(days=settings.export_retention_days)).timestamp()
    removed = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def run_retention(db: Database, settings: Settings) -> dict[str, Any]:
    stats = {"rawPurged": purge_raw_payloads(db, settings), "exportFilesPurged": purge_export_files(settings)}
    logger.info("retenção aplicada", extra=stats)
    return stats
