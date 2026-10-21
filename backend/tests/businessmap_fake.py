"""API Businessmap simulada (httpx.MockTransport) a partir das fixtures anonimizadas."""

import copy
import json
import re
from collections import defaultdict, deque
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "businessmap"
API_KEY = "test-key"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _ids(value: str | None) -> set[int] | None:
    if not value:
        return None
    return {int(v) for v in value.split(",") if v}


class FakeBusinessmap:
    def __init__(self, api_key: str = API_KEY):
        self.api_key = api_key
        self.boards = load_fixture("boards.json")["data"]
        self.structure = {96: load_fixture("current_structure_96.json")["data"]}
        self.cycle_time_columns = {96: load_fixture("cycle_time_columns_96.json")["data"]}
        self.users = load_fixture("users.json")["data"]
        self.card_types = load_fixture("card_types.json")["data"]
        self.api_limits = load_fixture("api_limits.json")["data"]
        self.cards = {
            "active": load_fixture("cards_active_96.json"),
            "archived": load_fixture("cards_archived_96.json"),
            "discarded": [],
        }
        self.requests: list[httpx.Request] = []
        self._failures: dict[str, deque] = defaultdict(deque)
        self.rate_headers = {"X-RateLimit-PerMinute-Remaining": "29", "X-RateLimit-PerHour-Remaining": "599"}

    def fail(self, path_regex: str, *responses: int | Exception | tuple[int, dict]) -> None:
        """Enfileira falhas (status, (status, headers) ou exceção) para pedidos cujo path coincide."""
        self._failures[path_regex].extend(responses)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def card(self, card_id: int) -> dict:
        for cards in self.cards.values():
            for c in cards:
                if c["card_id"] == card_id:
                    return c
        raise KeyError(card_id)

    def _ok(self, data) -> httpx.Response:
        return httpx.Response(200, json={"data": copy.deepcopy(data)}, headers=self.rate_headers)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/api/v2")
        for pattern, queue in self._failures.items():
            if queue and re.fullmatch(pattern, path):
                failure = queue.popleft()
                if isinstance(failure, Exception):
                    raise failure
                status, headers = failure if isinstance(failure, tuple) else (failure, {})
                return httpx.Response(status, json={"error": {"message": "falha simulada"}}, headers=headers)
        if request.headers.get("apikey") != self.api_key:
            return httpx.Response(401, json={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}})
        if request.method != "GET":
            return httpx.Response(405)
        q = request.url.params
        if path == "/boards":
            ids = _ids(q.get("board_ids"))
            return self._ok([b for b in self.boards if ids is None or b["board_id"] in ids])
        if m := re.fullmatch(r"/boards/(\d+)", path):
            board = next((b for b in self.boards if b["board_id"] == int(m[1])), None)
            return self._ok(board) if board else httpx.Response(404, json={"error": {"message": "Not found"}})
        if m := re.fullmatch(r"/boards/(\d+)/currentStructure", path):
            if int(m[1]) not in self.structure:
                return httpx.Response(404, json={"error": {"message": "Not found"}})
            return self._ok(self.structure[int(m[1])])
        if m := re.fullmatch(r"/boards/(\d+)/effectiveCycleTimeColumns", path):
            return self._ok(self.cycle_time_columns.get(int(m[1]), []))
        if path == "/users":
            return self._ok(self.users)
        if path == "/cardTypes":
            return self._ok(self.card_types)
        if path == "/apiLimits":
            return self._ok(self.api_limits)
        if path == "/cards":
            return self._cards(q)
        return httpx.Response(404, json={"error": {"message": f"rota simulada inexistente: {path}"}})

    def _cards(self, q: httpx.QueryParams) -> httpx.Response:
        state = q.get("state", "active")
        cards = self.cards[state]
        boards = _ids(q.get("board_ids"))
        card_ids = _ids(q.get("card_ids"))
        cards = [c for c in cards if (boards is None or c["board_id"] in boards) and (card_ids is None or c["card_id"] in card_ids)]
        per_page = min(int(q.get("per_page", 200)), 1000)
        page = int(q.get("page", 1))
        all_pages = max(1, -(-len(cards) // per_page))
        chunk = cards[(page - 1) * per_page : page * per_page]
        return self._ok(
            {"pagination": {"all_pages": all_pages, "current_page": page, "results_per_page": per_page}, "data": chunk}
        )
