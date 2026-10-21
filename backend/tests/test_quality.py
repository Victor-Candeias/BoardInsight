from datetime import UTC, datetime

PERIOD = {"from": "2026-09-01", "to": "2026-10-31", "granularity": "month"}


def at(month, day, hour=12):
    return datetime(2026, month, day, hour, tzinfo=UTC)


def event(db, card_id, key, **fields):
    db.card_events.insert_one({"boardId": 96, "cardId": card_id, "eventKey": key, "source": "sync", "type": "field_change"} | fields)


def test_current_blockers_with_reason_and_time(synced):
    body = synced.get("/api/v1/boards/96/blockers", params=PERIOD).json()
    cur = body["current"]
    assert (cur["blocked"], cur["openTotal"]) == (1, 4)
    assert cur["share"] == 0.25
    item = cur["items"][0]
    assert (item["cardId"], item["blockedDays"], item["reason"], item["comment"]) == (5003, 2.0, "Motivo 7", "Aguarda dependência externa")
    assert cur["byReason"] == [{"key": "Motivo 7", "label": "Motivo 7", "count": 1, "days": 2.0}]
    assert cur["byOwner"][0]["key"] == 12 and cur["days"]["p50"] == 2.0
    assert synced.get("/api/v1/boards/96/blockers", params={"ownerUserId": 11}).json()["current"]["blocked"] == 0


def test_observed_block_history_pairs_start_and_end(synced, db):
    event(db, 5002, "b1", field="isBlocked", **{"from": False, "to": True}, occurredAt=at(8, 30))
    event(db, 5002, "b2", field="isBlocked", **{"from": True, "to": False}, occurredAt=at(9, 3))
    event(db, 5004, "b3", field="isBlocked", **{"from": False, "to": True}, occurredAt=at(10, 2))
    hist = synced.get("/api/v1/boards/96/blockers", params=PERIOD).json()["history"]
    assert (hist["started"], hist["resolved"]) == (1, 1)
    assert [(s["started"], s["resolved"]) for s in hist["series"]] == [(0, 1), (1, 0)]
    assert hist["resolvedDays"]["count"] == 1 and hist["resolvedDays"]["p50"] == 4.0
    assert hist["historySince"] is not None
    other = synced.get("/api/v1/boards/96/blockers", params=PERIOD | {"ownerUserId": 12}).json()["history"]
    assert other["started"] == other["resolved"] == 0


def test_reopens_from_sync_and_api_are_not_double_counted(synced, db):
    event(db, 5005, "r1", field="status", **{"from": "done", "to": "in_progress"}, occurredAt=at(10, 6))
    db.card_events.insert_one(
        {"boardId": 96, "cardId": 5005, "eventKey": "r2", "source": "api", "type": "transition", "fromStatus": "done", "toStatus": "in_progress", "occurredAt": at(10, 5, 18)}
    )
    event(db, 5006, "r3", field="status", **{"from": "done", "to": "archived"}, occurredAt=at(10, 7))
    event(db, 5006, "r4", field="status", **{"from": "done", "to": "todo"}, occurredAt=at(9, 2))
    event(db, 5006, "r5", field="status", **{"from": "done", "to": "todo"}, occurredAt=at(10, 9))
    body = synced.get("/api/v1/boards/96/quality", params=PERIOD).json()
    assert body["available"] and body["completed"] == 2
    assert (body["reopens"], body["reopenedCards"], body["reopenRate"]) == (3, 2, 1.0)
    assert [i["cardId"] for i in body["items"]] == [5006, 5005]
    assert [s["reopens"] for s in body["series"]] == [1, 2]
    assert synced.get("/api/v1/boards/96/quality", params=PERIOD | {"ownerUserId": 13}).json()["reopens"] == 1


def test_quality_without_history_is_unavailable(synced, db):
    db.board_snapshots.delete_many({})
    body = synced.get("/api/v1/boards/96/quality").json()
    assert body["available"] is False and body["reason"] == "recolha de histórico ainda não iniciada"
    assert synced.get("/api/v1/boards/999/blockers").status_code == 404
