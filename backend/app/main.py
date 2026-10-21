from fastapi import FastAPI

from app import __version__
from app.api.v1 import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="BoardInsight API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
