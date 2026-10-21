from fastapi import APIRouter

from app.api.v1 import boards, meta, sync

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(sync.router)
api_router.include_router(boards.router)
