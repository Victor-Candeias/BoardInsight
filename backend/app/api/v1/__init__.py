from fastapi import APIRouter

from app.api.v1 import boards, cards, dashboard, delivery, meta, reports, sprints, sync

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(sync.router)
api_router.include_router(boards.router)
api_router.include_router(cards.router)
api_router.include_router(dashboard.router)
api_router.include_router(delivery.router)
api_router.include_router(sprints.router)
api_router.include_router(reports.router)
