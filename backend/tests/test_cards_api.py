from datetime import UTC, datetime, timedelta


def ids(response):
    assert response.status_code == 200, response.json()
    return [c["cardId"] for c in response.json()["items"]]


URL = "/api/v1/boards/96/cards"


def test_lists_active_cards_enriched(synced):
    body = synced.get(URL, params={"sort": "cardId"}).json()
    assert body["total"] == 6 and body["dataAsOf"] is not None
    first = body["items"][0]
    assert first["cardId"] == 5001 and "raw" not in first and "transitions" not in first
    card = next(c for c in body["items"] if c["cardId"] == 5003)
    assert card["ownerName"] and card["laneName"] and card["columnName"] and card["typeName"]
    assert card["statusLabel"] == "Em curso" and card["priorityLabel"] == "Crítica"


def test_filters(synced):
    assert ids(synced.get(URL, params={"status": "done", "sort": "cardId"})) == [5005, 5006]
    assert ids(synced.get(URL, params=[("status", "todo"), ("status", "backlog"), ("sort", "cardId")])) == [5001, 5002]
    assert ids(synced.get(URL, params={"open": "true", "sort": "cardId"})) == [5001, 5002, 5003, 5004]
    assert ids(synced.get(URL, params={"blocked": "true"})) == [5003]
    assert ids(synced.get(URL, params={"unassigned": "true"})) == [5001]
    assert ids(synced.get(URL, params=[("ownerUserId", 11), ("unassigned", "true"), ("sort", "cardId")])) == [5001, 5002, 5004]
    assert ids(synced.get(URL, params={"priority": 1})) == [5003]
    assert ids(synced.get(URL, params={"laneId": 3002})) == [5003]
    assert ids(synced.get(URL, params={"typeId": 42, "sort": "cardId"})) == [5003, 5006]
    assert ids(synced.get(URL, params={"q": "pesquisa"})) == [5002]
    assert ids(synced.get(URL, params={"q": "T-5004"})) == [5004]
    assert ids(synced.get(URL, params={"q": "5006"})) == [5006]
    assert ids(synced.get(URL, params={"q": "(.*"})) == []
    assert ids(synced.get(URL, params={"state": "archived"})) == [4001]
    assert synced.get(URL, params={"state": "all"}).json()["total"] == 7


def test_overdue_and_due_soon(synced, db):
    now = datetime.now(UTC)
    assert 5002 in ids(synced.get(URL, params={"overdue": "true"}))
    db.cards.update_one({"cardId": 5004}, {"$set": {"deadline": now + timedelta(days=2)}})
    assert ids(synced.get(URL, params={"dueSoon": "true"})) == [5004]
    items = {c["cardId"]: c for c in synced.get(URL).json()["items"]}
    assert items[5002]["overdue"] is True and items[5004]["dueSoon"] is True and items[5005]["overdue"] is False


def test_created_date_range_uses_local_days(synced, db):
    # 23:30 UTC de 31/03 = 00:30 de 01/04 em Lisboa (hora de verão).
    db.cards.update_one({"cardId": 5001}, {"$set": {"createdAt": datetime(2026, 3, 31, 23, 30, tzinfo=UTC)}})
    assert 5001 in ids(synced.get(URL, params={"createdFrom": "2026-04-01", "createdTo": "2026-04-01"}))
    assert 5001 not in ids(synced.get(URL, params={"createdFrom": "2026-03-31", "createdTo": "2026-03-31"}))


def test_missing_cards_hidden_by_default(synced, db):
    db.cards.update_one({"cardId": 5001}, {"$set": {"missingSince": datetime.now(UTC)}})
    assert 5001 not in ids(synced.get(URL))
    assert 5001 in ids(synced.get(URL, params={"includeMissing": "true"}))


def test_pagination_and_sorting(synced):
    page1 = synced.get(URL, params={"pageSize": 4, "sort": "-cardId"}).json()
    page2 = synced.get(URL, params={"pageSize": 4, "page": 2, "sort": "-cardId"}).json()
    assert [c["cardId"] for c in page1["items"]] == [5006, 5005, 5004, 5003]
    assert [c["cardId"] for c in page2["items"]] == [5002, 5001]
    assert page1["total"] == page2["total"] == 6


def test_invalid_params(synced):
    assert synced.get(URL, params={"sort": "raw"}).json()["error"]["code"] == "validation_error"
    assert synced.get(URL, params={"status": "xpto"}).status_code == 422
    assert synced.get(URL, params={"priority": 9}).status_code == 422
    assert synced.get(URL, params={"createdFrom": "2026-05-01", "createdTo": "2026-04-01"}).status_code == 422
    assert synced.get(URL, params={"pageSize": 1000}).status_code == 422
    assert synced.get("/api/v1/boards/1/cards").status_code == 404


def test_card_detail_with_transitions(synced):
    card = synced.get(f"{URL}/5004").json()
    assert card["title"] == "Rever API" and "raw" not in card
    assert [t["column_id"] for t in card["transitions"]] == [2003, 2004]
    assert all(t["columnName"] and t["laneName"] for t in card["transitions"])
    assert card["events"] == []
    assert synced.get(f"{URL}/999").json()["error"]["code"] == "card_not_found"


def test_filter_options(synced):
    opts = synced.get(f"{URL}/filter-options").json()
    assert {o["value"] for o in opts["owners"]} == {11, 12, 13}
    assert {o["value"] for o in opts["lanes"]} == {3001, 3002}
    assert {o["value"] for o in opts["types"]} == {41, 42, 43}
    assert len(opts["priorities"]) == 4
