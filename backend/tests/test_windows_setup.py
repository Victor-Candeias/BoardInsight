import asyncio

from app.core.config import REPO_ROOT, Settings
from app.ops.windows_setup import ensure_secret_file, prepare_env, read_env_value, register_board

TEMPLATE = REPO_ROOT / "deploy" / "windows" / "env.windows"


def test_prepare_env_creates_env_from_template(tmp_path):
    env = tmp_path / "data" / ".env"
    dist = r"C:\Program Files\BoardInsight\frontend\dist"
    prepare_env(env, TEMPLATE, url="https://cttv8.kanbanize.com/", board=96, port=8081, api_key=" chave ", frontend_dist=dist)

    settings = Settings(_env_file=env)
    assert settings.businessmap_base_url == "https://cttv8.kanbanize.com"
    assert settings.require_api_key() == "chave"
    assert (settings.businessmap_board_id, settings.app_port, settings.app_host) == (96, 8081, "0.0.0.0")
    assert str(settings.frontend_dist) == dist
    assert settings.export_dir == env.parent / "exports"
    assert len(settings.mongodb_password.get_secret_value()) >= 32
    assert "# BoardInsight (Windows)" in env.read_text(encoding="utf-8")


def test_prepare_env_upgrade_keeps_key_and_mongo_password(tmp_path):
    env = tmp_path / ".env"
    prepare_env(env, TEMPLATE, api_key="chave-original")
    password = read_env_value(env, "MONGODB_PASSWORD")

    prepare_env(env, TEMPLATE, board=120, api_key="")

    assert read_env_value(env, "BUSINESSMAP_API_KEY") == "chave-original"
    assert read_env_value(env, "MONGODB_PASSWORD") == password
    assert read_env_value(env, "BUSINESSMAP_BOARD_ID") == "120"
    assert env.read_text(encoding="utf-8").count("BUSINESSMAP_BOARD_ID=") == 1


def test_secret_file_is_generated_once(tmp_path):
    path = tmp_path / "mongodb-admin.secret"
    first = ensure_secret_file(path)
    assert len(first) >= 32 and ensure_secret_file(path) == first


def test_register_board_creates_board_and_sync_job_once(db, settings, client_factory):
    assert asyncio.run(register_board(db, settings, 96, client_factory)) is True
    assert db.boards.find_one({"boardId": 96})["name"] == "Team Board: Exemplo"
    assert db.jobs.find_one({"type": "sync_board"})["payload"] == {"boardId": 96}
    assert asyncio.run(register_board(db, settings, 96, client_factory)) is False
    assert db.jobs.count_documents({}) == 1
