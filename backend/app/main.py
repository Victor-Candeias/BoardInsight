import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.api.errors import install_error_handlers
from app.api.rate_limit import RateLimiter
from app.api.v1 import api_router
from app.api.v1 import auth as auth_api
from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.core.frontend import mount_frontend
from app.core.indexes import ensure_indexes
from app.core.logging import configure_logging
from app.core.middleware import OriginCheckMiddleware, RequestLoggingMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        ensure_indexes(get_database(), get_settings())
    except Exception:
        # A API arranca na mesma; /ready reporta o MongoDB indisponível.
        logger.exception("falha ao criar índices MongoDB")
    yield


def create_app(*, init_db: bool = True, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if init_db:
        configure_logging(settings)
    app = FastAPI(
        title="BoardInsight API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan if init_db else None,
    )
    app.state.rate_limiter = RateLimiter()
    # O último middleware adicionado é o mais exterior: logging > CORS > verificação de origem.
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.cors_origins)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID", "Retry-After", "Content-Disposition"],
            max_age=600,
        )
    app.add_middleware(RequestLoggingMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth_api.router, prefix="/api/v1")
    # Com AUTH_ENABLED=true todas as rotas /api/v1 (exceto /auth) exigem sessão; /health, /ready e a SPA ficam públicos.
    app.include_router(api_router, prefix="/api/v1", dependencies=[Depends(auth_api.require_user)])
    if settings.frontend_dist is not None:
        mount_frontend(app, settings.frontend_dist)
    return app


app = create_app()
