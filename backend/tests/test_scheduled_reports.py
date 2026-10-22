from datetime import UTC, datetime

from bson import ObjectId

from app.repositories.base import utcnow
from app.services.scheduled_reports import run_scheduled_reports

BASE = "/api/v1/reports"
CADENCE = {"cadence": {"start": "2026-09-28", "lengthDays": 14, "namePrefix": "Sprint"}, "explicit": []}


def at(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T10:00:00").replace(tzinfo=UTC)


def scheduled_definition(synced, db, since="2026-10-01", formats=("pdf", "xlsx")):
    db.boards.update_one({"boardId": 96}, {"$set": {"sprints": CADENCE}})
    body = {"boardId": 96, "name": "Equipa", "params": {"filters": {"status": "done"}}, "schedule": {"enabled": True, "formats": list(formats)}}
    definition = synced.post(BASE, json=body).json()
    db.report_definitions.update_one({"_id": ObjectId(definition["id"])}, {"$set": {"schedule.since": since}})
    return definition


def test_generates_each_ended_sprint_once(synced, db, settings):
    definition = scheduled_definition(synced, db)
    # Sprint 1 = 28/09–11/10 (terminada); Sprint 2 = 12/10–25/10 (atual)
    assert run_scheduled_reports(db, settings, at("2026-10-21")) == {"scheduledExports": 2}
    exports = list(db.report_exports.find({"definitionId": definition["id"]}))
    assert sorted(e["format"] for e in exports) == ["pdf", "xlsx"]
    first = exports[0]
    assert first["trigger"] == "schedule" and first["sprintId"] == "2026-09-28" and first["title"] == "Equipa — Sprint 1"
    assert first["params"]["from"] == "2026-09-28" and first["params"]["to"] == "2026-10-11"
    assert first["params"]["filters"]["status"] == ["done"]
    assert db.jobs.count_documents({"type": "report_export"}) == 2

    assert run_scheduled_reports(db, settings, at("2026-10-21")) == {"scheduledExports": 0}
    assert run_scheduled_reports(db, settings, at("2026-10-26")) == {"scheduledExports": 2}
    stored = synced.get(f"{BASE}/{definition['id']}").json()["schedule"]
    assert stored["lastSprintId"] == "2026-10-12" and len(stored["lastExportIds"]) == 2 and stored["lastError"] is None


def test_ignores_sprints_ended_before_activation_and_disabled(synced, db, settings):
    definition = scheduled_definition(synced, db, since="2026-10-12")
    assert run_scheduled_reports(db, settings, at("2026-10-21")) == {"scheduledExports": 0}
    synced.put(f"{BASE}/{definition['id']}", json={"name": "Equipa", "schedule": {"enabled": False, "formats": ["pdf"]}})
    assert run_scheduled_reports(db, settings, at("2026-10-26")) == {"scheduledExports": 0}


def test_errors_are_recorded_without_retrying(synced, db, settings):
    definition = scheduled_definition(synced, db)
    settings.export_pdf_max_rows = 0
    assert run_scheduled_reports(db, settings, at("2026-10-21")) == {"scheduledExports": 1}  # só o XLSX
    schedule = synced.get(f"{BASE}/{definition['id']}").json()["schedule"]
    assert schedule["lastError"]["code"] == "export_too_large" and schedule["lastSprintId"] == "2026-09-28"
    assert run_scheduled_reports(db, settings, at("2026-10-21")) == {"scheduledExports": 0}


def test_schedule_api_keeps_run_state(synced, db, settings):
    db.boards.update_one({"boardId": 96}, {"$set": {"sprints": CADENCE}})
    today = utcnow().astimezone(settings.tz).date().isoformat()
    created = synced.post(BASE, json={"boardId": 96, "name": "A", "schedule": {"enabled": True, "formats": ["pdf", "pdf"]}}).json()
    assert created["schedule"]["since"] == today and created["schedule"]["formats"] == ["pdf"]
    oid = ObjectId(created["id"])
    db.report_definitions.update_one({"_id": oid}, {"$set": {"schedule.since": "2026-01-01", "schedule.lastSprintId": "x"}})
    url = f"{BASE}/{created['id']}"
    kept = synced.put(url, json={"name": "A", "schedule": {"enabled": True, "formats": ["xlsx"]}}).json()["schedule"]
    assert kept["since"] == "2026-01-01" and kept["lastSprintId"] == "x" and kept["formats"] == ["xlsx"]
    assert synced.put(url, json={"name": "A", "schedule": {"enabled": False}}).json()["schedule"]["since"] is None
    assert synced.put(url, json={"name": "A", "schedule": {"enabled": True}}).json()["schedule"]["since"] == today
    assert synced.put(url, json={"name": "A", "schedule": {"enabled": True, "formats": []}}).status_code == 422
