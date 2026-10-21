import asyncio
import copy

from app.services.sync import SyncService

URL = "/api/v1/boards/96/cards"


def sync(db, settings, client_factory):
    result = asyncio.run(SyncService(db, settings, client_factory).sync_board(96))
    assert result.status == "success", result.error
    return result


def events(db, **query):
    return list(db.card_events.find({"boardId": 96, **query}, {"_id": 0}).sort([("cardId", 1), ("field", 1)]))


def test_first_sync_creates_snapshot_without_observed_events(db, settings, client_factory):
    result = sync(db, settings, client_factory)
    assert result.stats["eventsObserved"] == 0 and result.stats["snapshotCards"] == 6
    snap = db.board_snapshots.find_one({"boardId": 96})
    assert snap["byStatus"] == {"backlog": 1, "todo": 1, "in_progress": 2, "done": 2}
    assert snap["cardIds"]["in_progress"] == [5003, 5004] and snap["blocked"] == 1
    assert {c["key"]: c["count"] for c in snap["byColumn"]} == {2001: 1, 2002: 1, 2003: 1, 2004: 1, 2005: 2}
    assert events(db, source="sync") == []


def test_changes_between_syncs_become_events(db, settings, client_factory, fake_bm):
    sync(db, settings, client_factory)
    card = fake_bm.card(5002)
    card.update(column_id=2003, section=3, owner_user_id=12, is_blocked=1)
    new = copy.deepcopy(card) | {"card_id": 5007, "custom_id": "T-5007", "created_at": "2026-10-20T08:00:00Z"}
    fake_bm.cards["active"].append(new)
    fake_bm.cards["active"] = [c for c in fake_bm.cards["active"] if c["card_id"] != 5001]

    result = sync(db, settings, client_factory)
    changed = {(e["cardId"], e["field"]): (e.get("from"), e["to"]) for e in events(db, source="sync")}
    assert changed == {
        (5002, "columnId"): (2002, 2003),
        (5002, "isBlocked"): (False, True),
        (5002, "ownerUserId"): (11, 12),
        (5002, "section"): (2, 3),
        (5002, "status"): ("todo", "in_progress"),
        (5007, "created"): (None, 2003),
    }
    assert result.stats["eventsObserved"] == 6
    assert db.board_snapshots.count_documents({"boardId": 96}) == 2
    latest = db.board_snapshots.find_one({"boardId": 96}, sort=[("capturedAt", -1)])
    assert latest["cardIds"]["backlog"] == [] and 5001 not in latest["cardIds"]["in_progress"]  # 5001 em falta

    again = sync(db, settings, client_factory)
    assert again.stats["eventsObserved"] == 0 and len(events(db, source="sync")) == 6

    assert db.card_events.find_one({"cardId": 5002, "field": "columnId"})["previousObservedAt"] is not None


def test_api_transitions_are_recorded_once(db, settings, client_factory, fake_bm):
    fake_bm.card(5004)["transitions"] = [
        {"workflow_id": 1001, "column_id": 2002, "lane_id": 3001, "start": "2026-09-12T08:00:00Z", "end": "2026-10-01T09:00:00Z"},
        {"workflow_id": 1001, "column_id": 2004, "lane_id": 3001, "start": "2026-10-01T09:00:00Z", "end": None},
    ]
    assert sync(db, settings, client_factory).stats["eventsFromApi"] == 2
    api = events(db, source="api", cardId=5004)
    ordered = sorted(api, key=lambda e: e["occurredAt"])
    assert [(e["from"], e["to"], e["fromStatus"], e["toStatus"]) for e in ordered] == [
        (None, 2002, None, "todo"),
        (2002, 2004, "todo", "in_progress"),
    ]
    assert sync(db, settings, client_factory).stats["eventsFromApi"] == 0
    fake_bm.card(5004)["transitions"][1]["end"] = "2026-10-20T09:00:00Z"
    sync(db, settings, client_factory)
    assert len(events(db, source="api", cardId=5004)) == 2


def test_failed_sync_records_no_history(db, settings, client_factory, fake_bm):
    fake_bm.fail(r"/cards", 500, 500, 500, 500)
    result = asyncio.run(SyncService(db, settings, client_factory).sync_board(96))
    assert result.status == "error"
    assert db.board_snapshots.count_documents({}) == 0 and db.card_events.count_documents({}) == 0


def test_card_detail_shows_labelled_events_and_history_start(synced, db, settings, client_factory, fake_bm):
    fake_bm.card(5002).update(column_id=2003, section=3)
    sync(db, settings, client_factory)
    detail = synced.get(f"{URL}/5002").json()
    column = next(e for e in detail["events"] if e["field"] == "columnId")
    assert column["fieldLabel"] == "Coluna" and column["fromLabel"] and column["toLabel"] and column["fromLabel"] != column["toLabel"]
    status = next(e for e in detail["events"] if e["field"] == "status")
    assert (status["fromLabel"], status["toLabel"]) == ("A fazer", "Em curso")
    assert detail["snapshotsSince"] and detail["eventsSince"]
