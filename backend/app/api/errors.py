"""Formato de erro uniforme da API: `{"error": {"code", "message", "details"?}}`."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import ConfigurationError
from app.integrations.businessmap import (
    AuthenticationError,
    BusinessmapError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 429: "rate_limited"}

# Erros do Businessmap vistos pelo cliente da nossa API.
BUSINESSMAP_STATUS: list[tuple[type[BusinessmapError], int]] = [
    (AuthenticationError, 502),
    (PermissionDeniedError, 502),
    (NotFoundError, 404),
    (RateLimitError, 503),
]


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "erro HTTP"
        return JSONResponse(error_body(code, message), status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", ())), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(error_body("validation_error", "parâmetros inválidos", details), status_code=422)

    @app.exception_handler(BusinessmapError)
    async def _businessmap_error(_: Request, exc: BusinessmapError) -> JSONResponse:
        status = next((s for cls, s in BUSINESSMAP_STATUS if isinstance(exc, cls)), 502)
        logger.warning("erro Businessmap", extra={"error_code": exc.code, "bm_status": exc.status})
        code = exc.code if exc.code.startswith("businessmap") else f"businessmap_{exc.code}"
        return JSONResponse(error_body(code, exc.message), status_code=status)

    @app.exception_handler(ConfigurationError)
    async def _config_error(_: Request, exc: ConfigurationError) -> JSONResponse:
        return JSONResponse(error_body("configuration_error", str(exc)), status_code=503)
