from fastapi import APIRouter

from app.api.v1 import meta

api_router = APIRouter()
api_router.include_router(meta.router)
