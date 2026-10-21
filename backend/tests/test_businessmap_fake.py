import httpx

from tests.businessmap_fake import API_KEY, FakeBusinessmap


def _client(fake):
    return httpx.Client(transport=fake.transport(), base_url="https://example/api/v2", headers={"apikey": API_KEY})


def test_fake_paginates_cards():
    fake = FakeBusinessmap()
    with _client(fake) as c:
        first = c.get("/cards", params={"board_ids": "96", "per_page": 4, "page": 1}).json()["data"]
        second = c.get("/cards", params={"board_ids": "96", "per_page": 4, "page": 2}).json()["data"]
    assert first["pagination"]["all_pages"] == 2
    ids = [x["card_id"] for x in first["data"] + second["data"]]
    assert len(ids) == len(set(ids)) == 6


def test_fake_rejects_wrong_key_and_injects_failures():
    fake = FakeBusinessmap()
    with httpx.Client(transport=fake.transport(), base_url="https://example/api/v2") as c:
        assert c.get("/boards").status_code == 401
    fake.fail(r"/boards", 503)
    with _client(fake) as c:
        assert c.get("/boards").status_code == 503
        assert c.get("/boards").status_code == 200
