import os

import pytest

# Os testes nunca devem ler o `.env` real nem usar segredos reais.
os.environ["BOARDINSIGHT_ENV_FILE"] = os.devnull


@pytest.fixture
def settings_factory():
    from app.core.config import Settings

    def make(**overrides):
        return Settings(_env_file=None, **overrides)

    return make


@pytest.fixture
def db():
    import mongomock

    from app.core.config import Settings
    from app.core.indexes import ensure_indexes

    database = mongomock.MongoClient(tz_aware=True)["boardinsight_test"]
    ensure_indexes(database, Settings(_env_file=None))
    return database


@pytest.fixture
def settings(settings_factory, tmp_path):
    # Rate limit desligado por omissão nos testes; test_security.py ativa-o.
    return settings_factory(
        businessmap_api_key="test-key",
        export_dir=tmp_path / "exports",
        rate_limit_sync_per_minute=0,
        rate_limit_export_per_minute=0,
    )


@pytest.fixture
def client(db, settings, client_factory):
    from fastapi.testclient import TestClient

    from app.api.deps import get_client_factory
    from app.core.config import get_settings
    from app.core.database import get_database
    from app.main import create_app

    app = create_app(init_db=False)
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client_factory] = lambda: client_factory
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_bm():
    from tests.businessmap_fake import FakeBusinessmap

    return FakeBusinessmap()


@pytest.fixture
def client_factory(fake_bm):
    from app.integrations.businessmap import BusinessmapClient
    from tests.businessmap_fake import API_KEY

    async def no_sleep(_):
        return None

    def factory():
        return BusinessmapClient(
            "https://cttv8.example/api/v2", API_KEY, transport=fake_bm.transport(), sleep=no_sleep, max_retries=1
        )

    return factory


@pytest.fixture
def sync_service(db, settings, client_factory):
    from app.services.sync import SyncService

    return SyncService(db, settings, client_factory)


@pytest.fixture
def synced(client, db, settings, client_factory, fake_bm):
    import asyncio

    from app.services.sync import SyncService

    fake_bm.card(5004)["transitions"] = [
        {"workflow_id": 1001, "column_id": 2003, "lane_id": 3001, "start": "2026-09-01T09:00:00Z", "end": "2026-09-05T09:00:00Z"},
        {"workflow_id": 1001, "column_id": 2004, "lane_id": 3001, "start": "2026-09-05T09:00:00Z", "end": None},
    ]
    client.post("/api/v1/boards", json={"boardId": 96})
    assert asyncio.run(SyncService(db, settings, client_factory).sync_board(96)).status == "success"
    return client
