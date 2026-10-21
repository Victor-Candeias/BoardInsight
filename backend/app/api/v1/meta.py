from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["meta"])


@router.get("/version")
def version() -> dict[str, str]:
    return {"name": "BoardInsight", "version": __version__}
