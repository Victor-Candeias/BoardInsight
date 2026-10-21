"""Sincronização completa e idempotente de um board (README §9).

1. Lock por board (o timer de 30 min e o worker partilham o mesmo lock).
2. `sync_run` em execução.
3. Leitura de TODAS as páginas (ativos + arquivados recentes), com deduplicação.
4. Só depois de tudo lido: upserts em `cards`, hooks (eventos/snapshots), `lastSuccessfulSyncAt`.
5. Em falha nada é marcado como removido/concluído; o `sync_run` fica com o erro.
"""

import logging
import os
import socket
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from pydantic import ValidationError
from pymongo.database import Database

from app.core.config import Settings
from app.integrations.businessmap import BusinessmapClient, BusinessmapError
from app.models.businessmap import BmCard, BmUser
from app.models.cards import CardState, normalize_card
from app.repositories.base import utcnow
from app.repositories.boards import BoardRepository
from app.repositories.cards import CardRepository
from app.repositories.locks import LockRepository
from app.repositories.sync_runs import SyncRunRepository
from app.repositories.users import UserCacheRepository
from app.services.boards import fetch_board_metadata

logger = logging.getLogger(__name__)

ClientFactory = Callable[[], BusinessmapClient]


class SyncHook(Protocol):
    def __call__(
        self, db: Database, board: dict[str, Any], previous: dict[int, dict[str, Any]], current: list[dict[str, Any]], now: datetime
    ) -> dict[str, Any]: ...


@dataclass
class SyncResult:
    board_id: int
    status: str  # success | error | skipped
    run_id: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None


def lock_name(board_id: int) -> str:
    return f"sync:{board_id}"


class SyncService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        client_factory: ClientFactory | None = None,
        hooks: list[SyncHook] | None = None,
    ):
        self.db = db
        self.settings = settings
        self.client_factory = client_factory or (lambda: BusinessmapClient.from_settings(settings))
        self.hooks = hooks if hooks is not None else default_hooks()
        self.boards = BoardRepository(db)
        self.cards = CardRepository(db)
        self.runs = SyncRunRepository(db)
        self.locks = LockRepository(db)
        self.users = UserCacheRepository(db)
        self.owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

    async def sync_board(self, board_id: int, *, trigger: str = "timer", job_id: str | None = None) -> SyncResult:
        ttl = timedelta(minutes=self.settings.sync_lock_ttl_minutes)
        if not self.locks.acquire(lock_name(board_id), self.owner, ttl):
            logger.info("sync ignorada: board em sincronização", extra={"board_id": board_id, "trigger": trigger})
            return SyncResult(board_id, "skipped", error={"code": "locked", "message": "sincronização já em curso"})
        run_id = self.runs.start(board_id, trigger, job_id)
        stats: dict[str, Any] = {}
        try:
            async with self.client_factory() as client:
                stats = await self._run(client, board_id)
                stats["requests"] = client.request_count
            self.runs.finish(run_id, "success", stats)
            logger.info("sync concluída", extra={"board_id": board_id, "run_id": run_id, **stats})
            return SyncResult(board_id, "success", run_id, stats)
        except Exception as exc:
            error = {
                "code": exc.code if isinstance(exc, BusinessmapError) else "internal_error",
                "message": exc.message if isinstance(exc, BusinessmapError) else type(exc).__name__,
            }
            self.runs.finish(run_id, "error", stats, error)
            self.boards.update(board_id, {"lastSyncAt": utcnow(), "lastSyncStatus": "error", "lastSyncError": error})
            logger.exception("sync falhou", extra={"board_id": board_id, "run_id": run_id})
            return SyncResult(board_id, "error", run_id, stats, error)
        finally:
            self.locks.release(lock_name(board_id), self.owner)

    async def _fetch_cards(self, client: BusinessmapClient, board_id: int, state: CardState, **filters: Any) -> tuple[dict[int, dict], int, int]:
        cards: dict[int, dict[str, Any]] = {}
        duplicates = 0
        pages = 0
        async for page in client.iter_card_pages(board_id, state=state, per_page=self.settings.businessmap_page_size, **filters):
            pages += 1
            for raw in page.cards:
                card_id = raw.get("card_id")
                if card_id in cards:
                    duplicates += 1
                cards[card_id] = raw
        return cards, pages, duplicates

    async def _run(self, client: BusinessmapClient, board_id: int) -> dict[str, Any]:
        metadata = await fetch_board_metadata(client, board_id)
        users: list[dict[str, Any]] = []
        try:
            users = [
                {"userId": u.user_id, "name": u.display_name, "username": u.username}
                for u in (BmUser.model_validate(r) for r in await client.get_users())
            ]
        except BusinessmapError as exc:
            metadata["metadataWarnings"].append(f"utilizadores indisponíveis ({exc.code})")

        active, active_pages, dup_active = await self._fetch_cards(client, board_id, "active")
        since = utcnow() - timedelta(days=self.settings.retention_history_days)
        archived, archived_pages, dup_archived = await self._fetch_cards(
            client, board_id, "archived", archived_from=since.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

        # Todas as páginas foram lidas: a partir daqui pode escrever-se.
        now = utcnow()
        board = self.boards.upsert_metadata(board_id, metadata)
        columns = {c["columnId"]: c for c in metadata["structure"]["columns"]}
        docs: list[dict[str, Any]] = []
        invalid: list[int] = []
        for state, batch in (("archived", archived), ("active", active)):
            for card_id, raw in batch.items():
                try:
                    card = BmCard.model_validate(raw)
                except ValidationError:
                    invalid.append(card_id)
                    continue
                docs.append(normalize_card(card, state=state, columns=columns, base_url=self.settings.businessmap_base_url, raw=raw))
        # Um cartão ativo prevalece sobre uma cópia arquivada no mesmo resultado.
        docs = list({d["cardId"]: d for d in docs}.values())

        previous = self.cards.by_ids(board_id, [d["cardId"] for d in docs])
        previously_active = self.cards.active_ids(board_id)
        write = self.cards.upsert_many(docs, now)
        # Cartões que deixaram de aparecer não são apagados nem dados como concluídos.
        seen = set(active) | set(archived)
        missing = self.cards.mark_missing(board_id, sorted(previously_active - seen - set(invalid)), now)
        if users:
            self.users.replace_for_board(board_id, users)

        hook_stats: dict[str, Any] = {}
        for hook in self.hooks:
            hook_stats.update(hook(self.db, board, previous, docs, now))

        self.boards.update(
            board_id,
            {
                "lastSyncAt": now,
                "lastSuccessfulSyncAt": now,
                "lastSyncStatus": "success",
                "lastSyncError": None,
                "cardCount": len(active),
            },
        )
        return {
            "activePages": active_pages,
            "archivedPages": archived_pages,
            "activeCards": len(active),
            "archivedCards": len(archived),
            "duplicates": dup_active + dup_archived,
            "invalidCards": invalid,
            "upserted": write["upserted"],
            "modified": write["modified"],
            "missing": missing,
            "warnings": metadata["metadataWarnings"],
            **hook_stats,
        }

    async def sync_all(self, *, trigger: str = "timer") -> list[SyncResult]:
        return [await self.sync_board(board_id, trigger=trigger) for board_id in self.boards.enabled_ids()]


def default_hooks() -> list[SyncHook]:
    return []

