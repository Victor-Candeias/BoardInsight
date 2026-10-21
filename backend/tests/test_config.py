import pytest

from app.core.config import ConfigurationError


def test_secrets_are_not_exposed_in_repr(settings_factory):
    settings = settings_factory(businessmap_api_key="super-secret-key", mongodb_password="pw-123")
    text = repr(settings) + str(settings.model_dump())
    assert "super-secret-key" not in text
    assert "pw-123" not in text
    assert set(settings.secret_values()) == {"super-secret-key", "pw-123"}


def test_require_api_key_fails_when_missing(settings_factory):
    with pytest.raises(ConfigurationError):
        settings_factory(businessmap_api_key="").require_api_key()


def test_mongo_uri_is_composed_and_quoted(settings_factory):
    settings = settings_factory(
        mongodb_username="user@x", mongodb_password="p:w/d", mongodb_auth_source="BoardInsight"
    )
    assert settings.mongo_connection_uri() == "mongodb://user%40x:p%3Aw%2Fd@127.0.0.1:27017/?authSource=BoardInsight"


def test_explicit_mongo_uri_wins(settings_factory):
    settings = settings_factory(mongodb_uri="mongodb://h:1/", mongodb_username="ignored")
    assert settings.mongo_connection_uri() == "mongodb://h:1/"


def test_cors_origins_accepts_comma_separated(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", "http://a.lan, http://b.lan")
    assert Settings(_env_file=None).cors_origins == ["http://a.lan", "http://b.lan"]


def test_invalid_timezone_rejected(settings_factory):
    with pytest.raises(ValueError):
        settings_factory(app_timezone="Mars/Olympus")
