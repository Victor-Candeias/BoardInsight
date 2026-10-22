import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.rate_limit import RateLimiter
from app.core.config import get_settings
from app.core.database import get_database
from app.main import create_app


def test_rate_limiter_sliding_window():
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert limiter.hit("export", "a", 2) is None
    now[0] = 10
    assert limiter.hit("export", "a", 2) is None
    assert limiter.hit("export", "a", 2) == pytest.approx(50)
    assert limiter.hit("export", "b", 2) is None and limiter.hit("sync", "a", 2) is None
    now[0] = 60
    assert limiter.hit("export", "a", 2) is None
    assert limiter.hit("export", "a", 2) == pytest.approx(10)


def test_sync_and_export_are_rate_limited(synced, settings):
    settings.rate_limit_sync_per_minute = 1
    settings.rate_limit_export_per_minute = 2
    assert synced.post("/api/v1/boards/96/sync").status_code in (200, 202)
    limited = synced.post("/api/v1/boards/96/sync")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(limited.headers["retry-after"]) <= 60

    assert synced.get("/api/v1/boards/96/cards/export").status_code == 200
    assert synced.post("/api/v1/reports/export", json={"boardId": 96, "format": "xlsx"}).status_code == 202
    assert synced.post("/api/v1/reports/export", json={"boardId": 96, "format": "pdf"}).status_code == 429
    # Leituras normais não contam.
    assert synced.get("/api/v1/boards/96/cards").status_code == 200

    settings.rate_limit_export_per_minute = 0
    assert synced.get("/api/v1/boards/96/cards/export").status_code == 200


def make_client(db, settings) -> TestClient:
    app = create_app(init_db=False, settings=settings)
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app, base_url="http://boardinsight.lan")


def test_cors_only_for_configured_origins(db, settings):
    settings.cors_origins = ["http://dev.lan:5180"]
    client = make_client(db, settings)
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = client.options("/api/v1/boards", headers={"Origin": "http://dev.lan:5180", **preflight})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://dev.lan:5180"
    denied = client.options("/api/v1/boards", headers={"Origin": "http://evil.example", **preflight})
    assert "access-control-allow-origin" not in denied.headers
    assert "access-control-allow-origin" not in client.get("/api/v1/boards", headers={"Origin": "http://evil.example"}).headers


def test_writes_from_foreign_origins_are_rejected(db, settings):
    settings.cors_origins = ["http://dev.lan:5180"]
    client = make_client(db, settings)
    body = {"boardId": 96}
    foreign = client.post("/api/v1/boards", json=body, headers={"Origin": "http://evil.example"})
    assert foreign.status_code == 403 and foreign.json()["error"]["code"] == "origin_not_allowed"
    assert client.delete("/api/v1/reports/x", headers={"Origin": "http://boardinsight.lan.evil.example"}).status_code == 403
    # Mesma origem (Host), origem configurada, pedidos sem Origin e leituras passam.
    for headers in ({"Origin": "http://boardinsight.lan"}, {"Origin": "http://dev.lan:5180"}, {}):
        assert client.post("/api/v1/boards", json=body, headers=headers).status_code != 403
    assert client.get("/api/v1/boards", headers={"Origin": "http://evil.example"}).status_code == 200


@pytest.mark.parametrize("value", ["*", "http://a.lan,*", '["null"]'])
def test_cors_wildcard_is_rejected(settings_factory, value):
    with pytest.raises(ValidationError):
        settings_factory(cors_origins=value)
