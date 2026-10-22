from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.api.v1.common import board_or_404
from app.repositories.base import utcnow
from app.repositories.jobs import JobRepository
from app.repositories.report_exports import ReportExportRepository
from app.services.card_query import build_query
from app.services.reports import MEDIA_TYPES, ReportFormat, ReportParams, export_path, row_limit

router = APIRouter(prefix="/reports", tags=["reports"])


class ExportRequest(ReportParams):
    boardId: int
    format: ReportFormat


def public(db: DB, export: dict[str, Any]) -> dict[str, Any]:
    export = dict(export)
    if export["status"] in ("pending", "running") and export.get("jobId"):
        # Job interrompido (worker morreu / timeout) sem atualizar a exportação.
        job = JobRepository(db).get(export["jobId"])
        if job and job["status"] == "error":
            export.update(status="error", error=job["error"])
    done = export["status"] == "done"
    export["downloadUrl"] = f"/api/v1/reports/exports/{export['id']}/download" if done else None
    return export


def export_or_404(db: DB, export_id: str) -> dict[str, Any]:
    export = ReportExportRepository(db).get(export_id)
    if export is None:
        raise ApiError(404, "export_not_found", "exportação inexistente ou expirada")
    return public(db, export)


@router.post("/export", status_code=status.HTTP_202_ACCEPTED)
def create_export(body: ExportRequest, db: DB, settings: AppSettings) -> dict[str, Any]:
    """Valida e enfileira a geração (job `report_export`); o ficheiro é descarregado depois."""
    board_or_404(db, body.boardId)
    total = db.cards.count_documents(build_query(body.boardId, body.filters.to_card_filters(), settings.tz))
    limit = row_limit(settings, body.format)
    if total > limit:
        raise ApiError(422, "export_too_large", f"{total} cartões excedem o máximo de {limit} para {body.format.upper()}; refine os filtros")
    params = body.model_dump(mode="json", by_alias=True, exclude={"boardId", "format"})
    repo = ReportExportRepository(db)
    export = repo.create(
        {"boardId": body.boardId, "format": body.format, "report": "general", "title": body.title or "Relatório geral", "params": params},
        timedelta(days=settings.export_retention_days),
    )
    job, _ = JobRepository(db).enqueue("report_export", {"exportId": export["id"]}, dedupe=False)
    repo.update(export["id"], {"jobId": job["id"]})
    return public(db, {**export, "jobId": job["id"]})


@router.get("/exports")
def list_exports(
    db: DB, board_id: int | None = Query(None, alias="boardId"), limit: int = Query(20, ge=1, le=100)
) -> list[dict[str, Any]]:
    return [public(db, e) for e in ReportExportRepository(db).recent(board_id, limit)]


@router.get("/exports/{export_id}")
def get_export(export_id: str, db: DB) -> dict[str, Any]:
    return export_or_404(db, export_id)


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, db: DB, settings: AppSettings) -> FileResponse:
    export = export_or_404(db, export_id)
    if export["expiresAt"] <= utcnow():
        raise ApiError(410, "export_expired", "o ficheiro expirou; gere novamente o relatório")
    if export["status"] == "error":
        raise ApiError(409, "export_failed", (export.get("error") or {}).get("message") or "a geração falhou")
    if export["status"] != "done":
        raise ApiError(409, "export_not_ready", "o relatório ainda está a ser gerado")
    path = export_path(settings, export)
    if not path.is_file():
        raise ApiError(410, "export_expired", "o ficheiro já não existe; gere novamente o relatório")
    return FileResponse(path, media_type=MEDIA_TYPES[export["format"]], filename=export["fileName"])
