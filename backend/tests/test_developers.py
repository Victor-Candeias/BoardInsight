from datetime import UTC, datetime

URL = "/api/v1/boards/96/developers"
PERIOD = {"from": "2026-08-01", "to": "2026-10-31", "granularity": "month"}


def by_user(body):
    return {d["userId"]: d for d in body["developers"]}


def test_developers_open_work_completed_and_aging(synced, db):
    db.cards.update_one({"cardId": 5001}, {"$set": {"coOwnerIds": [12]}})
    db.cards.update_one({"cardId": 5004}, {"$set": {"firstStartTime": None, "inCurrentPositionSince": datetime.now(UTC)}})
    body = synced.get(URL, params=PERIOD).json()
    assert "não são uma avaliação" in body["disclaimer"].lower()
    assert [b["label"] for b in body["buckets"]] == ["ago 2026", "set 2026", "out 2026"]
    rows = by_user(body)

    ana = rows[11]
    assert (ana["todo"], ana["inProgress"], ana["open"], ana["overdue"], ana["completed"]) == (1, 1, 2, 1, 1)
    assert ana["completedSeries"] == [1, 0, 0]  # 4001 arquivado
    assert ana["agingEstimated"] is True and ana["avgAgingDays"] < 1

    bruno = rows[12]
    assert (bruno["inProgress"], bruno["blocked"], bruno["coOwnedOpen"], bruno["completed"]) == (1, 1, 1, 1)
    assert bruno["completedSeries"] == [0, 1, 0] and bruno["agingEstimated"] is False
    expected_age = (datetime.now(UTC) - datetime(2026, 9, 20, 9, tzinfo=UTC)).total_seconds() / 86400
    assert abs(bruno["avgAgingDays"] - expected_age) < 0.2

    assert (rows[13]["completed"], rows[13]["completedSize"], rows[13]["open"]) == (1, 8, 0)
    assert rows[None]["name"] == "Sem responsável" and rows[None]["backlog"] == 1
    assert body["developers"][-1]["userId"] is None


def test_developers_ignore_owner_filter_but_apply_others(synced):
    rows = by_user(synced.get(URL, params={**PERIOD, "ownerUserId": 11, "typeId": 42}).json())
    assert set(rows) == {12}
    assert synced.get("/api/v1/boards/1/developers").status_code == 404
