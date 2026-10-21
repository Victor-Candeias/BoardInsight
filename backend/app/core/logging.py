"""Logging estruturado (JSON numa linha para o journald) sem segredos.

Todas as mensagens passam por um filtro que substitui os valores dos segredos
configurados e padrões comuns de credenciais (`apikey`, `password`, URIs MongoDB).
"""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

REDACTED = "***"
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_PATTERNS = [
    re.compile(r"(?i)(apikey|api_key|api-key|password|passwd|secret|token)(\"?\s*[:=]\s*\"?)([^\s\"',&}]+)"),
    re.compile(r"(mongodb(?:\+srv)?://[^:/\s]+:)([^@\s]+)(@)"),
]
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime", "taskName", "color_message"}


class Redactor:
    def __init__(self, secrets: list[str] | None = None):
        self.secrets = sorted({s for s in (secrets or []) if len(s) >= 4}, key=len, reverse=True)

    def __call__(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, REDACTED)
        text = _PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
        text = _PATTERNS[1].sub(lambda m: f"{m.group(1)}{REDACTED}{m.group(3)}", text)
        return text

    def value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self(value)
        if isinstance(value, dict):
            return {k: REDACTED if _is_secret_key(k) else self.value(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [self.value(v) for v in value]
        return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(word in lowered for word in ("apikey", "api_key", "password", "secret", "token"))


class JsonFormatter(logging.Formatter):
    def __init__(self, redactor: Redactor):
        super().__init__()
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": self.redactor(record.getMessage()),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = REDACTED if _is_secret_key(key) else self.redactor.value(value)
        if record.exc_info:
            payload["exc"] = self.redactor(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(Redactor(settings.secret_values())))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.app_log_level.upper())
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    # O middleware de pedidos substitui o access log do uvicorn.
    logging.getLogger("uvicorn.access").disabled = True
    # Nunca registar cabeçalhos/URLs de pedidos externos ao nível DEBUG.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
