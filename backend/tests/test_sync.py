import asyncio
from datetime import timedelta

from app.repositories.locks import LockRepository
from app.services.sync import lock_name


def run(coro):
    return asyncio.run(coro)


def test_full_sync_imports_cards_and_metadata(db, sync_service, fake_bm):
    result = run(sync_service.sync_board(96, trigger="manual"))
    assert result.status == "success", result.error
    assert result.stats["activeCards"] == 6 and result.stats["archivedCards"] == 1
    assert db.cards.count_documents({"boardId": 96}) == 7
    board = db.boards.find_one({"boardId": 96})
    assert board["name"] == "Team Board: Exemplo"
    assert board["lastSuccessfulSyncAt"] is not None
    assert board["cycleTimeColumnIds"] == [2003, 2004]
    assert {t["name"] for t in board["cardTypes"]} == {"Tarefa", "Bug", "História"}
    assert db.users_cache.count_documents({"boardId": 96}) == 3
    archived_requests = [r for r in fake_bm.requests if r.url.params.get("state") == "archived"]
    assert archived_requests and "archived_from" in archived_requests[0].url.params
    run_doc = db.sync_runs.find_one()
    assert run_doc["status"] == "success" and run_doc["trigger"] == "manual"


def test_sync_is_idempotent(db, sync_service):
    run(sync_service.sync_board(96))
    first = {d["cardId"]: d["firstSeenAt"] for d in db.cards.find()}
    result = run(sync_service.sync_board(96))
    assert result.stats["upserted"] == 0
    assert db.cards.count_documents({}) == 7
    assert {d["cardId"]: d["firstSeenAt"] for d in db.cards.find()} == first


def test_failure_keeps_previous_data(db, sync_service, fake_bm):
    run(sync_service.sync_board(96))
    before_sync = db.boards.find_one({"boardId": 96})["lastSuccessfulSyncAt"]
    fake_bm.cards["active"][0]["section"] = 4
    fake_bm.fail(r"/cards", 500, 500)
    result = run(sync_service.sync_board(96))
    assert result.status == "error" and result.error["code"] == "unavailable"
    assert db.cards.find_one({"cardId": 5001})["status"] == "backlog"
    board = db.boards.find_one({"boardId": 96})
    assert board["lastSuccessfulSyncAt"] == before_sync
    assert board["lastSyncStatus"] == "error"
    assert db.sync_runs.find_one({"status": "error"})["error"]["code"] == "unavailable"
    assert not LockRepository(db).is_locked(lock_name(96))


def test_failure_on_second_page_aborts_before_writing(db, sync_service, fake_bm, settings):
    settings.businessmap_page_size = 4
    calls = {"n": 0}
    original = fake_bm.handle

    def handle(request):
        if request.url.path.endswith("/cards") and request.url.params.get("page") == "2":
            calls["n"] += 1
            import httpx

            return httpx.Response(503)
        return original(request)

    fake_bm.handle = handle
    result = run(sync_service.sync_board(96))
    assert result.status == "error"
    assert calls["n"] == 2  # tentativa + 1 retry
    assert db.cards.count_documents({}) == 0


def test_concurrent_sync_is_skipped(db, sync_service):
    LockRepository(db).acquire(lock_name(96), "other-process", timedelta(minutes=5))
    result = run(sync_service.sync_board(96))
    assert result.status == "skipped"
    assert db.sync_runs.count_documents({}) == 0


def test_expired_lock_is_taken_over(db, sync_service):
    LockRepository(db).acquire(lock_name(96), "dead-process", timedelta(seconds=-1))
    assert run(sync_service.sync_board(96)).status == "success"


def test_cards_that_disappear_are_flagged_not_removed(db, sync_service, fake_bm):
    run(sync_service.sync_board(96))
    fake_bm.cards["active"] = [c for c in fake_bm.cards["active"] if c["card_id"] != 5004]
    result = run(sync_service.sync_board(96))
    assert result.stats["missing"] == 1
    card = db.cards.find_one({"cardId": 5004})
    assert card["missingSince"] is not None and card["status"] == "in_progress"


def test_invalid_card_is_reported_and_skipped(db, sync_service, fake_bm):
    fake_bm.cards["active"].append({"card_id": 9999, "board_id": 96, "created_at": "não é uma data"})
    result = run(sync_service.sync_board(96))
    assert result.status == "success"
    assert result.stats["invalidCards"] == [9999]
    assert db.cards.count_documents({}) == 7
