"""Configuração da aplicação, lida de variáveis de ambiente e do ficheiro `.env`.

Os segredos (API Key Businessmap, password MongoDB) são `SecretStr`: não aparecem em
`repr()`, logs nem respostas da API.
"""

from functools import lru_cache
from typing import Annotated
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class ConfigurationError(RuntimeError):
    """Configuração obrigatória em falta ou inválida."""


def _env_files() -> tuple[Path, ...]:
    import os

    explicit = os.environ.get("BOARDINSIGHT_ENV_FILE")
    if explicit:
        return (Path(explicit),)
    return (REPO_ROOT / ".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "production"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_log_level: str = "INFO"
    app_timezone: str = "Europe/Lisbon"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    mongodb_uri: SecretStr | None = None
    mongodb_host: str = "127.0.0.1"
    mongodb_port: int = 27017
    mongodb_database: str = "BoardInsight"
    mongodb_username: str | None = None
    mongodb_password: SecretStr | None = None
    mongodb_auth_source: str | None = None
    mongodb_timeout_ms: int = 5000

    businessmap_base_url: str = "https://cttv8.kanbanize.com"
    businessmap_api_key: SecretStr | None = None
    businessmap_board_id: int = 96
    businessmap_timeout_seconds: float = 30.0
    businessmap_max_retries: int = 4
    businessmap_page_size: int = 200

    sync_interval_minutes: int = 30
    sync_lock_ttl_minutes: int = 20
    stale_after_minutes: int = 90

    worker_poll_seconds: float = 2.0
    job_timeout_minutes: int = 30
    job_retention_days: int = 7

    export_dir: Path = Path("/var/lib/boardinsight/exports")
    export_retention_days: int = 30
    export_max_rows: int = 50_000
    export_pdf_max_rows: int = 2_000

    retention_history_days: int = 183
    retention_raw_days: int = 30
    retention_sync_runs_days: int = 90

    rate_limit_sync_per_minute: int = 2
    rate_limit_export_per_minute: int = 6

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                import json

                value = json.loads(value)
            else:
                value = [o.strip() for o in value.split(",") if o.strip()]
        if isinstance(value, list) and any(str(o).strip() in {"*", "null"} for o in value):
            raise ValueError("CORS_ORIGINS tem de listar origens explícitas (sem '*' nem 'null')")
        return value

    @field_validator("app_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"timezone inválida: {value}") from exc
        return value

    @field_validator("businessmap_base_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("businessmap_api_key", "mongodb_uri", "mongodb_password", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def businessmap_api_url(self) -> str:
        return f"{self.businessmap_base_url}/api/v2"

    def require_api_key(self) -> str:
        if self.businessmap_api_key is None:
            raise ConfigurationError("BUSINESSMAP_API_KEY não está definida no .env")
        return self.businessmap_api_key.get_secret_value()

    def mongo_connection_uri(self) -> str:
        """URI de ligação completa. Contém a password: nunca registar em logs."""
        if self.mongodb_uri is not None:
            return self.mongodb_uri.get_secret_value()
        auth = ""
        if self.mongodb_username:
            password = self.mongodb_password.get_secret_value() if self.mongodb_password else ""
            auth = f"{quote_plus(self.mongodb_username)}:{quote_plus(password)}@"
        query = f"?authSource={quote_plus(self.mongodb_auth_source)}" if self.mongodb_auth_source else ""
        return f"mongodb://{auth}{self.mongodb_host}:{self.mongodb_port}/{query}"

    def secret_values(self) -> list[str]:
        """Valores que nunca podem aparecer em logs (usado pelo filtro de redação)."""
        values = [self.businessmap_api_key, self.mongodb_password, self.mongodb_uri]
        return [v.get_secret_value() for v in values if v is not None and v.get_secret_value()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
