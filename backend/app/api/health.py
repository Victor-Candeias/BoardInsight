from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import DB, AppSettings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: DB, settings: AppSettings) -> JSONResponse:
    checks: dict[str, dict[str, object]] = {}
    try:
        db.command("ping")
        checks["mongodb"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001 - reportar qualquer falha de ligação
        checks["mongodb"] = {"ok": False, "error": type(exc).__name__}
    checks["businessmap_api_key"] = {"ok": settings.businessmap_api_key is not None}
    is_ready = all(c["ok"] for c in checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "not_ready", "checks": checks},
    )
