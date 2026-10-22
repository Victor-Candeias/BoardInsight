import asyncio
import os
import time
from datetime import timedelta

from app.jobs.worker import Worker
from app.repositories.base import utcnow
from app.repositories.boards import BoardRepository
from app.repositories.jobs import JobRepository
from app.services.retention import run_retention


def add_board(db, board_id=96):
    BoardRepository(db).upsert_metadata(board_id, {"name": "Team Board: Exemplo"})


def test_enqueue_sync_requires_configured_board(client):
    response = client.post("/api/v1/boards/96/sync")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "board_not_found", "message": "o board 96 não está configurado"}}


def test_enqueue_sync_dedupes_active_job(client, db):
    add_board(db)
    first = client.post("/api/v1/boards/96/sync")
    assert first.status_code == 202 and first.json()["created"] is True
    second = client.post("/api/v1/boards/96/sync")
    assert second.status_code == 200 and second.json()["created"] is False
    assert second.json()["job"]["id"] == first.json()["job"]["id"]
    job = client.get(f"/api/v1/jobs/{first.json()['job']['id']}").json()
    assert job["status"] == "pending" and job["payload"] == {"boardId": 96}


def test_enqueue_without_api_key_is_configuration_error(client, db, settings):
    add_board(db)
    settings.businessmap_api_key = None
    response = client.post("/api/v1/boards/96/sync")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "configuration_error"


def test_error_format_for_unknown_job_and_validation(client):
    assert client.get("/api/v1/jobs/nao-e-id").json()["error"]["code"] == "job_not_found"
    response = client.post("/api/v1/boards/abc/sync")
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"
    assert client.get("/api/v1/nada").json()["error"]["code"] == "not_found"


def test_worker_runs_sync_job(db, settings, client_factory, client):
    add_board(db)
    job_id = client.post("/api/v1/boards/96/sync").json()["job"]["id"]
    worker = Worker(db, settings, client_factory=client_factory)
    assert asyncio.run(worker.run_one())["id"] == job_id
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "done" and job["result"]["stats"]["activeCards"] == 6
    assert db.sync_runs.find_one()["jobId"] == job_id
    status = client.get("/api/v1/boards/96/sync-status").json()
    assert status["lastSyncStatus"] == "success" and status["stale"] is False and status["running"] is False
    assert asyncio.run(worker.run_one()) is None


def test_worker_records_sync_failure(db, settings, client_factory, fake_bm):
    add_board(db)
    job, _ = JobRepository(db).enqueue("sync_board", {"boardId": 96})
    fake_bm.fail(r"/cards", 503, 503)
    asyncio.run(Worker(db, settings, client_factory=client_factory).run_one())
    stored = JobRepository(db).get(job["id"])
    assert stored["status"] == "error" and stored["error"]["code"] == "unavailable"
    assert stored["expiresAt"] > utcnow()


def test_worker_handles_unknown_type_and_crashing_handler(db, settings):
    jobs = JobRepository(db)
    unknown, _ = jobs.enqueue("nao_existe", {})

    async def boom(*_):
        raise RuntimeError("x")

    crash, _ = jobs.enqueue("boom", {})
    worker = Worker(db, settings, handlers={"boom": boom})
    asyncio.run(worker.run_one())
    asyncio.run(worker.run_one())
    assert jobs.get(unknown["id"])["error"]["code"] == "unknown_job_type"
    assert jobs.get(crash["id"])["error"]["code"] == "internal_error"


def test_stale_running_jobs_are_failed(db):
    jobs = JobRepository(db)
    job, _ = jobs.enqueue("sync_board", {"boardId": 1})
    jobs.claim("w")
    db.jobs.update_one({}, {"$set": {"startedAt": utcnow() - timedelta(hours=2)}})
    assert jobs.fail_stale(timedelta(minutes=30)) == 1
    assert jobs.get(job["id"])["error"]["code"] == "timeout"


def test_retention_purges_old_raw_and_exports(db, settings):
    old = utcnow() - timedelta(days=settings.retention_raw_days + 1)
    db.cards.insert_many(
        [
            {"boardId": 96, "cardId": 1, "raw": {"a": 1}, "rawUpdatedAt": old},
            {"boardId": 96, "cardId": 2, "raw": {"a": 2}, "rawUpdatedAt": utcnow()},
        ]
    )
    settings.export_dir.mkdir(parents=True)
    expired = settings.export_dir / "antigo.csv"
    fresh = settings.export_dir / "novo.csv"
    expired.write_text("x")
    fresh.write_text("y")
    past = time.time() - (settings.export_retention_days + 1) * 86400
    os.utime(expired, (past, past))
    assert run_retention(db, settings) == {"rawPurged": 1, "exportFilesPurged": 1}
    assert "raw" not in db.cards.find_one({"cardId": 1}) and "raw" in db.cards.find_one({"cardId": 2})
    assert not expired.exists() and fresh.exists()


def test_stop_handlers_fall_back_to_signal_without_add_signal_handler(monkeypatch):
    import signal

    from app.jobs.worker import install_stop_handlers

    registered = {}
    monkeypatch.setattr(signal, "signal", lambda sig, handler: registered.__setitem__(sig, handler))

    class WindowsLoop:
        def add_signal_handler(self, *_):
            raise NotImplementedError

        def call_soon_threadsafe(self, callback):
            callback()

    stopped = []
    install_stop_handlers(WindowsLoop(), lambda: stopped.append(True))
    assert set(registered) == {signal.SIGTERM, signal.SIGINT}
    registered[signal.SIGINT](signal.SIGINT, None)
    assert stopped == [True]
