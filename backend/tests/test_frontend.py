from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import ConfigurationError, get_settings
from app.core.database import get_database
from app.core.frontend import mount_frontend
from app.main import create_app


@pytest.fixture
def dist(tmp_path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "brand").mkdir()
    (root / "index.html").write_text("<html>BoardInsight</html>")
    (root / "assets" / "index-abc123.js").write_text("console.log(1)")
    (root / "brand" / "logo.svg").write_text("<svg/>")
    (tmp_path / "segredo.txt").write_text("não servir")
    return root


@pytest.fixture
def web(db, settings, dist):
    settings.frontend_dist = dist
    app = create_app(init_db=False, settings=settings)
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client


def test_index_and_spa_routes_without_cache(web):
    for path in ("/", "/boards/96/dashboard"):
        response = web.get(path)
        assert response.status_code == 200
        assert "BoardInsight" in response.text
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-frame-options"] == "DENY"


def test_assets_are_immutable_and_missing_assets_404(web):
    response = web.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]
    assert web.get("/assets/nao-existe.js").status_code == 404
    assert web.get("/brand/logo.svg").text == "<svg/>"


def test_api_routes_are_not_shadowed(web):
    assert web.get("/api/v1/version").json()["name"] == "BoardInsight"
    assert web.get("/health").json() == {"status": "ok"}
    response = web.get("/api/v1/nao-existe")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_path_traversal_never_leaves_dist(web):
    for path in ("/..%2Fsegredo.txt", "/assets/..%2F..%2Fsegredo.txt"):
        assert "não servir" not in web.get(path).text


def test_frontend_is_off_by_default(client):
    assert client.get("/").status_code == 404


def test_empty_frontend_dist_is_off_and_missing_index_fails(settings_factory, tmp_path):
    assert settings_factory(frontend_dist="").frontend_dist is None
    with pytest.raises(ConfigurationError):
        mount_frontend(create_app(init_db=False, settings=settings_factory()), tmp_path)
