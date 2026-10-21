from datetime import UTC, datetime, timedelta

BASE = "/api/v1/boards/96"


def test_throughput_by_month_includes_archived_and_sizes(synced):
    body = synced.get(f"{BASE}/throughput", params={"from": "2026-08-01", "to": "2026-10-31", "granularity": "month"}).json()
    assert [(s["label"], s["count"], s["size"], s["partial"]) for s in body["series"]] == [
        ("ago 2026", 1, 2, False),
        ("set 2026", 1, 1, False),
        ("out 2026", 1, 8, False),
    ]
    assert (body["total"], body["totalSize"], body["averagePerBucket"]) == (3, 11, 1)
    assert sum(t["count"] for t in body["byType"]) == 3


def test_throughput_partial_buckets_filters_and_discarded(synced, db):
    params = {"from": "2026-09-30", "to": "2026-10-11", "granularity": "week"}
    body = synced.get(f"{BASE}/throughput", params=params).json()
    assert [(s["bucket"], s["count"], s["partial"]) for s in body["series"]] == [("2026-09-28", 1, True), ("2026-10-05", 1, False)]
    assert body["averagePerBucket"] == 1

    assert synced.get(f"{BASE}/throughput", params={**params, "ownerUserId": 13}).json()["total"] == 1
    db.cards.update_one({"cardId": 5005}, {"$set": {"status": "discarded"}})
    assert synced.get(f"{BASE}/throughput", params=params).json()["total"] == 1


def test_deadlines_lists_overdue_and_due_soon(synced, db):
    soon = datetime.now(UTC) + timedelta(days=2)
    db.cards.update_one({"cardId": 5003}, {"$set": {"deadline": soon}})
    db.cards.update_one({"cardId": 5005}, {"$set": {"deadline": datetime(2026, 1, 1, tzinfo=UTC)}})  # concluído: ignorado
    body = synced.get(f"{BASE}/deadlines").json()
    assert [c["cardId"] for c in body["overdue"]["items"]] == [5002]
    assert body["overdue"]["items"][0]["daysToDeadline"] < 0 and body["overdue"]["items"][0]["overdue"] is True
    assert [c["cardId"] for c in body["dueSoon"]["items"]] == [5003]
    assert 1 < body["dueSoon"]["items"][0]["daysToDeadline"] <= 2
    assert body["overdueByOwner"] == [{"key": 11, "label": body["overdue"]["items"][0]["ownerName"], "count": 1}]
    assert (body["openTotal"], body["withoutDeadline"], body["dueSoonDays"]) == (4, 1, 7)

    assert synced.get(f"{BASE}/deadlines", params={"ownerUserId": 12}).json()["overdue"]["total"] == 0
    assert synced.get(f"{BASE}/deadlines", params={"overdue": "true"}).json()["dueSoon"]["total"] == 1
    assert synced.get("/api/v1/boards/1/deadlines").status_code == 404
