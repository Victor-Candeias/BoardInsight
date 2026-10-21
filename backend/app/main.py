import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import health
from app.api.errors import install_error_handlers
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import get_database
from app.core.indexes import ensure_indexes
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        ensure_indexes(get_database(), get_settings())
    except Exception:
        # A API arranca na mesma; /ready reporta o MongoDB indisponível.
        logger.exception("falha ao criar índices MongoDB")
    yield


def create_app(*, init_db: bool = True) -> FastAPI:
    if init_db:
        configure_logging(get_settings())
    app = FastAPI(
        title="BoardInsight API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan if init_db else None,
    )
    app.add_middleware(RequestLoggingMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
