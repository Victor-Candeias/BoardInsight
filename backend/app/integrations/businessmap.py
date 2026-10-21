"""Cliente da API REST v2 do Businessmap (só leitura).

- `httpx.AsyncClient` com `base_url`, timeout e cabeçalho `apikey` (lido do `.env`).
- Retry com backoff exponencial para timeouts, erros de rede, 429 e 5xx; respeita
  `Retry-After` e os cabeçalhos `X-RateLimit-*` (a API não documenta `Retry-After`).
- Erros normalizados (`BusinessmapError` e subclasses).
- Logs com path, board, estado HTTP e duração — nunca cabeçalhos nem a chave.
"""

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_PER_PAGE = 1000

CARD_FIELDS = [
    "card_id", "custom_id", "board_id", "workflow_id", "title", "owner_user_id", "type_id", "size",
    "priority", "color", "deadline", "reporter", "created_at", "revision", "last_modified",
    "in_current_position_since", "section", "column_id", "lane_id", "position", "last_column_id",
    "last_lane_id", "archived_at", "discarded_at", "is_blocked", "block_reason", "current_block_time",
    "current_logged_time", "current_cycle_time", "first_request_time", "first_start_time",
    "first_end_time", "last_request_time", "last_start_time", "last_end_time",
]
CARD_EXPAND = ["co_owner_ids", "tag_ids", "transitions"]


class BusinessmapError(Exception):
    code = "businessmap_error"
    retryable = False

    def __init__(self, message: str, *, status: int | None = None, path: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.path = path


class AuthenticationError(BusinessmapError):
    code = "authentication_failed"


class PermissionDeniedError(BusinessmapError):
    code = "permission_denied"


class NotFoundError(BusinessmapError):
    code = "not_found"


class RateLimitError(BusinessmapError):
    code = "rate_limited"
    retryable = True


class UnavailableError(BusinessmapError):
    code = "unavailable"
    retryable = True


class UnexpectedResponseError(BusinessmapError):
    code = "unexpected_response"


_STATUS_ERRORS: dict[int, type[BusinessmapError]] = {
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    429: RateLimitError,
}


@dataclass
class RateLimitState:
    per_minute_remaining: int | None = None
    per_hour_remaining: int | None = None


@dataclass
class CardPage:
    cards: list[dict[str, Any]]
    current_page: int
    all_pages: int


def _csv(values: Iterable[Any] | None) -> str | None:
    if values is None:
        return None
    joined = ",".join(str(v) for v in values)
    return joined or None


def _int_header(response: httpx.Response, name: str) -> int | None:
    try:
        return int(response.headers[name])
    except (KeyError, ValueError):
        return None


class BusinessmapClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        backoff_max: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"apikey": api_key, "Accept": "application/json", "User-Agent": "BoardInsight/0.1"},
            timeout=timeout,
            transport=transport,
        )
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._sleep = sleep
        self.rate_limit = RateLimitState()
        self.request_count = 0

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> "BusinessmapClient":
        return cls(
            settings.businessmap_api_url,
            settings.require_api_key(),
            timeout=settings.businessmap_timeout_seconds,
            max_retries=settings.businessmap_max_retries,
            **kwargs,
        )

    async def __aenter__(self) -> "BusinessmapClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # -- núcleo -------------------------------------------------------------------------

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return min(float(retry_after), self.backoff_max)
            if response.status_code == 429 and _int_header(response, "X-RateLimit-PerMinute-Remaining") == 0:
                return self.backoff_max
        delay = self.backoff_base * (2**attempt)
        return min(delay + random.uniform(0, self.backoff_base), self.backoff_max)

    def _track_rate_limit(self, response: httpx.Response) -> None:
        minute = _int_header(response, "X-RateLimit-PerMinute-Remaining")
        hour = _int_header(response, "X-RateLimit-PerHour-Remaining")
        if minute is not None:
            self.rate_limit.per_minute_remaining = minute
        if hour is not None:
            self.rate_limit.per_hour_remaining = hour

    async def _throttle(self) -> None:
        # Pausa preventiva quando a quota do minuto está esgotada.
        if self.rate_limit.per_minute_remaining == 0:
            logger.warning("quota por minuto esgotada; a aguardar", extra={"wait_s": 60})
            await self._sleep(60)
            self.rate_limit.per_minute_remaining = None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        attempt = 0
        while True:
            await self._throttle()
            started = time.perf_counter()
            response: httpx.Response | None = None
            error: BusinessmapError | None = None
            try:
                self.request_count += 1
                response = await self._http.get(path, params=params)
                self._track_rate_limit(response)
            except httpx.TimeoutException:
                error = UnavailableError("timeout ao contactar o Businessmap", path=path)
            except httpx.TransportError as exc:
                error = UnavailableError(f"erro de rede: {type(exc).__name__}", path=path)
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            status = response.status_code if response is not None else None
            logger.info(
                "businessmap GET",
                extra={
                    "path": path,
                    "board_ids": params.get("board_ids"),
                    "page": params.get("page"),
                    "status": status,
                    "duration_ms": duration_ms,
                    "attempt": attempt + 1,
                },
            )
            if response is not None and response.is_success:
                return self._parse(response, path)
            if response is not None:
                error_cls = _STATUS_ERRORS.get(response.status_code)
                if error_cls is None:
                    error_cls = UnavailableError if response.status_code >= 500 else BusinessmapError
                error = error_cls(self._error_message(response), status=response.status_code, path=path)
            assert error is not None
            retryable = error.retryable or (status in RETRYABLE_STATUS)
            if not retryable or attempt >= self.max_retries:
                raise error
            delay = self._delay(attempt, response)
            logger.warning(
                "businessmap retry", extra={"path": path, "status": status, "delay_s": round(delay, 2), "attempt": attempt + 1}
            )
            await self._sleep(delay)
            self.rate_limit.per_minute_remaining = None
            attempt += 1

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
            message = (body.get("error") or {}).get("message") if isinstance(body, dict) else None
        except ValueError:
            message = None
        return f"HTTP {response.status_code}" + (f": {message}" if message else "")

    @staticmethod
    def _parse(response: httpx.Response, path: str) -> Any:
        try:
            body = response.json()
        except ValueError as exc:
            raise UnexpectedResponseError("resposta não é JSON", status=response.status_code, path=path) from exc
        if not isinstance(body, dict) or "data" not in body:
            raise UnexpectedResponseError("resposta sem campo 'data'", status=response.status_code, path=path)
        return body["data"]

    @staticmethod
    def _expect(value: Any, kind: type, path: str) -> Any:
        if not isinstance(value, kind):
            raise UnexpectedResponseError(f"esperado {kind.__name__} em 'data'", path=path)
        return value

    # -- endpoints ----------------------------------------------------------------------

    async def get_boards(self, board_ids: Iterable[int] | None = None) -> list[dict[str, Any]]:
        data = await self.get("/boards", {"board_ids": _csv(board_ids), "fields": "board_id,workspace_id,is_archived,name,revision"})
        return self._expect(data, list, "/boards")

    async def get_board(self, board_id: int) -> dict[str, Any]:
        boards = await self.get_boards([board_id])
        board = next((b for b in boards if b.get("board_id") == board_id), None)
        if board is None:
            raise NotFoundError(f"board {board_id} não encontrado ou sem acesso", status=404, path="/boards")
        return board

    async def get_board_structure(self, board_id: int) -> dict[str, Any]:
        path = f"/boards/{board_id}/currentStructure"
        return self._expect(await self.get(path), dict, path)

    async def get_cycle_time_columns(self, board_id: int) -> list[dict[str, Any]]:
        path = f"/boards/{board_id}/effectiveCycleTimeColumns"
        return self._expect(await self.get(path), list, path)

    async def get_users(self) -> list[dict[str, Any]]:
        return self._expect(await self.get("/users", {"fields": "user_id,username,realname"}), list, "/users")

    async def get_card_types(self) -> list[dict[str, Any]]:
        return self._expect(await self.get("/cardTypes"), list, "/cardTypes")

    async def get_api_limits(self) -> list[dict[str, Any]]:
        return self._expect(await self.get("/apiLimits"), list, "/apiLimits")

    async def list_cards(
        self,
        board_id: int,
        *,
        state: str = "active",
        page: int = 1,
        per_page: int = 200,
        fields: Iterable[str] | None = CARD_FIELDS,
        expand: Iterable[str] | None = CARD_EXPAND,
        card_ids: Iterable[int] | None = None,
        **filters: Any,
    ) -> CardPage:
        params = {
            "board_ids": str(board_id),
            "state": state,
            "page": page,
            "per_page": min(per_page, MAX_PER_PAGE),
            "fields": _csv(fields),
            "expand": _csv(expand),
            "card_ids": _csv(card_ids),
            **filters,
        }
        data = self._expect(await self.get("/cards", params), dict, "/cards")
        pagination = data.get("pagination")
        cards = data.get("data")
        if not isinstance(pagination, dict) or not isinstance(cards, list):
            raise UnexpectedResponseError("paginação/lista de cartões em falta", path="/cards")
        try:
            all_pages = int(pagination["all_pages"])
            current = int(pagination.get("current_page", page))
        except (KeyError, TypeError, ValueError) as exc:
            raise UnexpectedResponseError("paginação inválida", path="/cards") from exc
        return CardPage(cards=cards, current_page=current, all_pages=all_pages)

    async def iter_card_pages(self, board_id: int, **kwargs: Any) -> AsyncIterator[CardPage]:
        page = 1
        while True:
            result = await self.list_cards(board_id, page=page, **kwargs)
            yield result
            if page >= result.all_pages or not result.cards:
                return
            page += 1

    async def get_cards_by_ids(self, board_id: int, card_ids: list[int], **kwargs: Any) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for start in range(0, len(card_ids), 100):
            async for result in self.iter_card_pages(board_id, card_ids=card_ids[start : start + 100], **kwargs):
                cards.extend(result.cards)
        return cards
