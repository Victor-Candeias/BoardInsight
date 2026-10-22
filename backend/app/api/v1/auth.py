"""Login com email e password do domínio e sessão por cookie (G9).

Com `AUTH_ENABLED=false` (desenvolvimento, Debian) tudo fica aberto como antes e `/auth/me` indica-o.
"""

import logging
import math
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.api.rate_limit import RateLimiter
from app.repositories.auth_sessions import AuthSessionRepository
from app.services.auth import AuthError, AuthUser, Directory, LdapDirectory

logger = logging.getLogger(__name__)

SESSION_COOKIE = "boardinsight_session"
LOGIN_BUCKET = "login"
LOGIN_WINDOW_SECONDS = 15 * 60.0

router = APIRouter(prefix="/auth", tags=["auth"])


def get_directory(settings: AppSettings) -> Directory:
    return LdapDirectory(settings)


def require_user(request: Request, db: DB, settings: AppSettings) -> AuthUser | None:
    """Dependência das rotas da API: sem sessão válida responde 401 (no-op com a autenticação desligada)."""
    if not settings.auth_enabled:
        return None
    user = AuthSessionRepository(db).get(
        request.cookies.get(SESSION_COOKIE, ""), timedelta(minutes=settings.auth_session_ttl_minutes)
    )
    if user is None:
        raise ApiError(401, "unauthenticated", "sessão inexistente ou expirada; inicie sessão")
    request.state.user = user
    return user


CurrentUser = Annotated[AuthUser | None, Depends(require_user)]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=1, max_length=1024, repr=False)


def _check_login_rate(limiter: RateLimiter, keys: list[str], limit: int) -> None:
    waits = [w for w in (limiter.check(LOGIN_BUCKET, k, limit, LOGIN_WINDOW_SECONDS) for k in keys) if w is not None]
    if waits:
        seconds = max(1, math.ceil(max(waits)))
        raise ApiError(
            429,
            "too_many_attempts",
            f"demasiadas tentativas falhadas; tente novamente dentro de {math.ceil(seconds / 60)} min",
            {"retryAfterSeconds": seconds},
            headers={"Retry-After": str(seconds)},
        )


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DB,
    settings: AppSettings,
    directory: Annotated[Directory, Depends(get_directory)],
) -> dict:
    if not settings.auth_enabled:
        raise ApiError(404, "auth_disabled", "a autenticação não está ativa")
    email = body.email.strip().lower()
    client = request.client.host if request.client else "unknown"
    keys = [f"email:{email}", f"ip:{client}"]
    limiter: RateLimiter = request.app.state.rate_limiter
    _check_login_rate(limiter, keys, settings.auth_max_failed_logins)
    try:
        user = directory.authenticate(email, body.password)
    except AuthError as exc:
        if exc.status == 401:
            for key in keys:
                limiter.record(LOGIN_BUCKET, key)
        logger.warning("login recusado", extra={"login": email, "reason": exc.code})
        raise ApiError(exc.status, exc.code, exc.message) from None
    limiter.reset(LOGIN_BUCKET, keys[0])
    max_age = timedelta(hours=settings.auth_session_max_hours)
    token = AuthSessionRepository(db).create(user, timedelta(minutes=settings.auth_session_ttl_minutes), max_age)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(max_age.total_seconds()),
        httponly=True,
        samesite="strict",
        path="/",
    )
    logger.info("login", extra={"login": user.username})
    return {"authEnabled": True, "user": user.to_api()}


@router.post("/logout", status_code=204)
def logout(request: Request, db: DB) -> Response:
    AuthSessionRepository(db).delete(request.cookies.get(SESSION_COOKIE, ""))
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    return response


@router.get("/me")
def me(request: Request, db: DB, settings: AppSettings) -> dict:
    if not settings.auth_enabled:
        return {"authEnabled": False, "user": None}
    user = require_user(request, db, settings)
    return {"authEnabled": True, "user": user.to_api() if user else None}
