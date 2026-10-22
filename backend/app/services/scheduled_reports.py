"""Relatórios agendados por sprint (F4): executados pelo timer de sync (`app.jobs.sync`).

Uma definição com `schedule.enabled` gera, depois de cada sprint terminar, um relatório por
formato com o período da sprint. Só conta sprints terminadas desde a ativação (`since`) e
cada sprint é gerada uma única vez (`lastSprintId`).
"""

import logging
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo.database import Database

from app.core.config import Settings
from app.repositories.base import utcnow
from app.repositories.report_definitions import ReportDefinitionRepository
from app.services.reports import ReportError, ReportFormat, ReportParams, enqueue_export
from app.services.sprints import list_sprints

logger = logging.getLogger(__name__)


class ScheduleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    trigger: Literal["sprint_end"] = "sprint_end"
    formats: list[ReportFormat] = Field(default_factory=lambda: ["pdf"], min_length=1)

    @field_validator("formats")
    @classmethod
    def _unique(cls, value: list[ReportFormat]) -> list[ReportFormat]:
        return list(dict.fromkeys(value))


def normalize_schedule(new: ScheduleConfig | None, old: dict[str, Any] | None, today: date) -> dict[str, Any] | None:
    """Guarda a configuração mantendo o estado de execução; `since` = dia da (re)ativação."""
    if new is None:
        return None
    old = old or {}
    since = old.get("since") if old.get("enabled") else None
    return {
        **new.model_dump(),
        "since": (since or today.isoformat()) if new.enabled else None,
        "lastSprintId": old.get("lastSprintId"),
        "lastRunAt": old.get("lastRunAt"),
        "lastExportIds": old.get("lastExportIds", []),
        "lastError": old.get("lastError"),
    }


def run_scheduled_reports(db: Database, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    today = now.astimezone(settings.tz).date()
    repo = ReportDefinitionRepository(db)
    created: list[str] = []
    for definition in repo.scheduled():
        schedule = definition["schedule"]
        board = db.boards.find_one({"boardId": definition["boardId"]})
        if board is None or board.get("enabled") is False:
            continue
        since = date.fromisoformat(schedule["since"])
        ended = [s for s in list_sprints(board.get("sprints"), today) if s["state"] == "past" and s["end"] >= since]
        if not ended or ended[-1]["id"] == schedule.get("lastSprintId"):
            continue
        sprint = ended[-1]
        params = ReportParams.model_validate(definition["params"]).model_copy(
            update={"date_from": sprint["start"], "date_to": sprint["end"], "title": f"{definition['name']} — {sprint['name']}"}
        )
        ids, error = [], None
        for fmt in schedule["formats"]:
            try:
                export = enqueue_export(
                    db,
                    settings,
                    definition["boardId"],
                    fmt,
                    params,
                    definition_id=definition["id"],
                    extra={"trigger": "schedule", "sprintId": sprint["id"], "sprintName": sprint["name"]},
                )
                ids.append(export["id"])
            except ReportError as exc:
                error = {"code": exc.code, "message": exc.message}
                logger.warning("relatório agendado não gerado", extra={"definition_id": definition["id"], "error_code": exc.code})
        # Mesmo com erro a sprint fica registada: não repetir a cada 30 minutos.
        repo.record_schedule_run(
            definition["id"], {"lastSprintId": sprint["id"], "lastRunAt": now, "lastExportIds": ids, "lastError": error}
        )
        created += ids
    stats = {"scheduledExports": len(created)}
    if created:
        logger.info("relatórios agendados enfileirados", extra=stats)
    return stats
