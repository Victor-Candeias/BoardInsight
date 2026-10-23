"""Índices e TTLs das collections (retenção definida em A3)."""

import logging
from dataclasses import dataclass, field

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.core.config import Settings

logger = logging.getLogger(__name__)
DAY = 86_400


@dataclass(frozen=True)
class IndexSpec:
    collection: str
    keys: list[tuple[str, int]]
    name: str
    options: dict = field(default_factory=dict)


def index_specs(settings: Settings) -> list[IndexSpec]:
    history_ttl = settings.retention_history_days * DAY
    return [
        IndexSpec("boards", [("boardId", ASCENDING)], "boardId_unique", {"unique": True}),
        IndexSpec("boards", [("workspaceId", ASCENDING)], "workspaceId"),
        IndexSpec("cards", [("boardId", ASCENDING), ("cardId", ASCENDING)], "board_card_unique", {"unique": True}),
        IndexSpec("cards", [("boardId", ASCENDING), ("state", ASCENDING), ("section", ASCENDING)], "board_state_section"),
        IndexSpec("cards", [("boardId", ASCENDING), ("ownerUserId", ASCENDING)], "board_owner"),
        IndexSpec("cards", [("boardId", ASCENDING), ("lastEndTime", DESCENDING)], "board_last_end"),
        IndexSpec("card_events", [("boardId", ASCENDING), ("cardId", ASCENDING), ("occurredAt", ASCENDING)], "board_card_time"),
        IndexSpec("card_events", [("eventKey", ASCENDING)], "eventKey_unique", {"unique": True}),
        IndexSpec("card_events", [("occurredAt", ASCENDING)], "occurredAt_ttl", {"expireAfterSeconds": history_ttl}),
        IndexSpec("board_snapshots", [("boardId", ASCENDING), ("capturedAt", ASCENDING)], "board_captured_unique", {"unique": True}),
        IndexSpec("board_snapshots", [("capturedAt", ASCENDING)], "capturedAt_ttl", {"expireAfterSeconds": history_ttl}),
        IndexSpec("sync_runs", [("boardId", ASCENDING), ("startedAt", DESCENDING)], "board_started"),
        IndexSpec("sync_runs", [("startedAt", ASCENDING)], "startedAt_ttl", {"expireAfterSeconds": settings.retention_sync_runs_days * DAY}),
        IndexSpec("locks", [("expiresAt", ASCENDING)], "expiresAt_ttl", {"expireAfterSeconds": 0}),
        IndexSpec("jobs", [("status", ASCENDING), ("createdAt", ASCENDING)], "status_created"),
        IndexSpec("jobs", [("expiresAt", ASCENDING)], "expiresAt_ttl", {"expireAfterSeconds": 0}),
        IndexSpec(
            "report_definitions", [("boardId", ASCENDING), ("name", ASCENDING)], "board_name_unique", {"unique": True}
        ),
        IndexSpec("report_exports", [("createdAt", DESCENDING)], "createdAt"),
        IndexSpec("report_exports", [("expiresAt", ASCENDING)], "expiresAt_ttl", {"expireAfterSeconds": 0}),
        IndexSpec("users_cache", [("boardId", ASCENDING), ("userId", ASCENDING)], "board_user_unique", {"unique": True}),
    IndexSpec("logged_times", [("boardId", ASCENDING), ("loggedTimeId", ASCENDING)], "board_logged_time_unique", {"unique": True}),
    IndexSpec("logged_times", [("boardId", ASCENDING), ("date", ASCENDING)], "board_date"),
    IndexSpec("logged_times", [("boardId", ASCENDING), ("userId", ASCENDING), ("date", ASCENDING)], "board_user_date"),
    IndexSpec("logged_times", [("date", ASCENDING)], "date_ttl", {"expireAfterSeconds": history_ttl}),
        IndexSpec("auth_sessions", [("expiresAt", ASCENDING)], "expiresAt_ttl", {"expireAfterSeconds": 0}),
    ]


# Índices substituídos (coleção, nome): removidos se ainda existirem.
OBSOLETE_INDEXES = [("report_definitions", "name_unique")]


def ensure_indexes(db: Database, settings: Settings) -> None:
    for collection_name, index_name in OBSOLETE_INDEXES:
        if index_name in db[collection_name].index_information():
            db[collection_name].drop_index(index_name)
            logger.info("índice obsoleto removido", extra={"collection": collection_name, "index": index_name})
    for spec in index_specs(settings):
        collection = db[spec.collection]
        try:
            collection.create_index(spec.keys, name=spec.name, **spec.options)
        except OperationFailure as exc:
            ttl = spec.options.get("expireAfterSeconds")
            # Mudança de retenção num índice TTL existente: atualizar com collMod.
            if ttl is not None and exc.code in (85, 86):
                db.command(
                    "collMod",
                    spec.collection,
                    index={"keyPattern": dict(spec.keys), "expireAfterSeconds": ttl},
                )
                logger.info("ttl atualizado", extra={"collection": spec.collection, "index": spec.name})
            else:
                raise
