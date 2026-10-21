import asyncio
import logging
import os

import httpx
import pytest

from app.integrations.businessmap import (
    AuthenticationError,
    BusinessmapClient,
    NotFoundError,
    PermissionDeniedError,
    UnavailableError,
    UnexpectedResponseError,
)
from tests.businessmap_fake import API_KEY, FakeBusinessmap


def run(coro):
    return asyncio.run(coro)


def make_client(fake, key=API_KEY, max_retries=3):
    sleeps: list[float] = []

    async def sleep(seconds):
        sleeps.append(seconds)

    client = BusinessmapClient(
        "https://example/api/v2", key, transport=fake.transport(), max_retries=max_retries, sleep=sleep, backoff_base=0.5
    )
    return client, sleeps


def test_get_board_96():
    fake = FakeBusinessmap()
    client, _ = make_client(fake)
    board = run(client.get_board(96))
    assert board["workspace_id"] == 35
    assert fake.requests[0].url.params["board_ids"] == "96"
    assert fake.requests[0].headers["apikey"] == API_KEY


def test_wrong_key_is_not_retried():
    fake = FakeBusinessmap()
    client, sleeps = make_client(fake, key="wrong")
    with pytest.raises(AuthenticationError) as exc:
        run(client.get_board(96))
    assert exc.value.status == 401
    assert len(fake.requests) == 1 and sleeps == []


@pytest.mark.parametrize("status,error", [(403, PermissionDeniedError), (404, NotFoundError)])
def test_client_errors_are_normalized(status, error):
    fake = FakeBusinessmap()
    fake.fail(r"/boards/96/currentStructure", status)
    client, _ = make_client(fake)
    with pytest.raises(error):
        run(client.get_board_structure(96))


def test_unknown_board_is_not_found():
    client, _ = make_client(FakeBusinessmap())
    with pytest.raises(NotFoundError):
        run(client.get_board(12345))


def test_transient_errors_are_retried_with_backoff():
    fake = FakeBusinessmap()
    fake.fail(r"/boards", 503, 502)
    client, sleeps = make_client(fake)
    assert run(client.get_boards([96]))[0]["board_id"] == 96
    assert len(fake.requests) == 3
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0] - 0.5


def test_rate_limit_respects_retry_after_and_headers():
    fake = FakeBusinessmap()
    fake.fail(r"/boards", (429, {"Retry-After": "7"}), (429, {"X-RateLimit-PerMinute-Remaining": "0"}))
    client, sleeps = make_client(fake)
    run(client.get_boards())
    assert sleeps == [7.0, 60.0]


def test_timeouts_exhaust_retries():
    fake = FakeBusinessmap()
    fake.fail(r"/boards", *[httpx.ReadTimeout("t")] * 3)
    client, sleeps = make_client(fake, max_retries=2)
    with pytest.raises(UnavailableError):
        run(client.get_boards())
    assert len(sleeps) == 2


def test_unexpected_payload():
    def handler(request):
        return httpx.Response(200, json={"nope": []})

    client = BusinessmapClient("https://example/api/v2", API_KEY, transport=httpx.MockTransport(handler))
    with pytest.raises(UnexpectedResponseError):
        run(client.get_boards())


def test_iterates_all_card_pages():
    fake = FakeBusinessmap()
    client, _ = make_client(fake)

    async def collect():
        pages = [p async for p in client.iter_card_pages(96, per_page=4)]
        return pages

    pages = run(collect())
    assert [p.current_page for p in pages] == [1, 2]
    assert sum(len(p.cards) for p in pages) == 6
    assert "transitions" in fake.requests[0].url.params["expand"]


def test_api_key_never_logged(caplog):
    fake = FakeBusinessmap()
    fake.fail(r"/boards", 500)
    client, _ = make_client(fake)
    with caplog.at_level(logging.DEBUG):
        run(client.get_boards())
    dump = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert API_KEY not in dump
    assert any(getattr(r, "status", None) == 500 for r in caplog.records)


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("BUSINESSMAP_API_KEY"), reason="BUSINESSMAP_API_KEY não definida")
def test_live_board_96():
    from app.core.config import Settings

    settings = Settings()

    async def check():
        async with BusinessmapClient.from_settings(settings) as client:
            board = await client.get_board(settings.businessmap_default_board_id)
            page = await client.list_cards(board["board_id"], per_page=1)
            return board, page

    board, page = run(check())
    assert board["board_id"] == 96 and board["workspace_id"] == 35
    assert page.all_pages >= 1
