from typing import Any

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.api.v1.common import board_or_404
from app.api.rate_limit import rate_limit
from app.repositories.base import utcnow
from app.repositories.jobs import JobRepository
from app.repositories.report_definitions import DuplicateName, ReportDefinitionRepository
from app.repositories.report_exports import ReportExportRepository
from app.services.card_query import CardEnricher
from app.services.scheduled_reports import ScheduleConfig, normalize_schedule
from app.services.reports import (
    MEDIA_TYPES,
    ReportError,
    ReportFormat,
    ReportParams,
    describe_filters,
    enqueue_export,
    export_path,
)

router = APIRouter(prefix="/reports", tags=["reports"])


class ExportRequest(ReportParams):
    boardId: int
    format: ReportFormat


class DefinitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    params: ReportParams = Field(default_factory=ReportParams)
    schedule: ScheduleConfig | None = None


class DefinitionCreate(DefinitionUpdate):
    boardId: int


class DefinitionExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


def _enqueue(db: DB, settings: AppSettings, board_id: int, fmt: ReportFormat, params: ReportParams, **kwargs: Any) -> dict[str, Any]:
    try:
        return public(db, enqueue_export(db, settings, board_id, fmt, params, **kwargs))
    except ReportError as exc:
        raise ApiError(422, exc.code, exc.message) from None


@router.post("/export", status_code=status.HTTP_202_ACCEPTED, dependencies=[rate_limit("export")])
def create_export(body: ExportRequest, db: DB, settings: AppSettings) -> dict[str, Any]:
    """Valida e enfileira a geração (job `report_export`); o ficheiro é descarregado depois."""
    board_or_404(db, body.boardId)
    params = ReportParams.model_validate(body.model_dump(by_alias=True, exclude={"boardId", "format"}))
    return _enqueue(db, settings, body.boardId, body.format, params)


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


# --- Definições guardadas ----------------------------------------------------------------------


def _with_label(definitions: list[dict[str, Any]], enrich: CardEnricher) -> list[dict[str, Any]]:
    params = (ReportParams.model_validate(d["params"]) for d in definitions)
    return [{**d, "filtersLabel": describe_filters(p.filters, enrich)} for d, p in zip(definitions, params, strict=True)]


def definition_or_404(db: DB, definition_id: str) -> dict[str, Any]:
    definition = ReportDefinitionRepository(db).get(definition_id)
    if definition is None:
        raise ApiError(404, "report_not_found", "definição de relatório inexistente")
    return definition


def _name_taken(name: str) -> ApiError:
    return ApiError(409, "report_name_taken", f"já existe uma definição chamada «{name}» neste board")


@router.get("")
def list_definitions(db: DB, board_id: int = Query(alias="boardId")) -> list[dict[str, Any]]:
    board = board_or_404(db, board_id)
    return _with_label(ReportDefinitionRepository(db).for_board(board_id), CardEnricher(db, board))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_definition(body: DefinitionCreate, db: DB, settings: AppSettings) -> dict[str, Any]:
    board = board_or_404(db, body.boardId)
    name = body.name.strip()
    schedule = normalize_schedule(body.schedule, None, utcnow().astimezone(settings.tz).date())
    try:
        created = ReportDefinitionRepository(db).create(body.boardId, name, body.params.model_dump(mode="json", by_alias=True), schedule)
    except DuplicateName:
        raise _name_taken(name) from None
    return _with_label([created], CardEnricher(db, board))[0]


@router.get("/{definition_id}")
def get_definition(definition_id: str, db: DB) -> dict[str, Any]:
    definition = definition_or_404(db, definition_id)
    return _with_label([definition], CardEnricher(db, board_or_404(db, definition["boardId"])))[0]


@router.put("/{definition_id}")
def update_definition(definition_id: str, body: DefinitionUpdate, db: DB, settings: AppSettings) -> dict[str, Any]:
    """Substitui nome, parâmetros e agendamento (o estado de execução do agendamento mantém-se)."""
    definition = definition_or_404(db, definition_id)
    name = body.name.strip()
    schedule = normalize_schedule(body.schedule, definition.get("schedule"), utcnow().astimezone(settings.tz).date())
    try:
        updated = ReportDefinitionRepository(db).update(
            definition_id, name, body.params.model_dump(mode="json", by_alias=True), schedule
        )
    except DuplicateName:
        raise _name_taken(name) from None
    return _with_label([updated], CardEnricher(db, board_or_404(db, definition["boardId"])))[0]


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_definition(definition_id: str, db: DB) -> Response:
    if not ReportDefinitionRepository(db).delete(definition_id):
        raise ApiError(404, "report_not_found", "definição de relatório inexistente")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{definition_id}/export", status_code=status.HTTP_202_ACCEPTED, dependencies=[rate_limit("export")])
def export_definition(definition_id: str, body: DefinitionExport, db: DB, settings: AppSettings) -> dict[str, Any]:
    """Gera o relatório de uma definição guardada (sem datas fixas, usa o último mês)."""
    definition = definition_or_404(db, definition_id)
    board_or_404(db, definition["boardId"])
    params = ReportParams.model_validate(definition["params"])
    return _enqueue(
        db, settings, definition["boardId"], body.format, params, definition_id=definition["id"], default_title=definition["name"]
    )
