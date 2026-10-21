from datetime import UTC, datetime

URL = "/api/v1/boards/96/cfd"
PERIOD = {"from": "2026-10-01", "to": "2026-10-03"}


def snap(at, ids, columns):
    return {
        "boardId": 96,
        "capturedAt": at,
        "total": sum(len(v) for v in ids.values()),
        "byStatus": {s: len(v) for s, v in ids.items()},
        "byColumn": [{"key": k, "count": len(v), "cardIds": v} for k, v in columns.items()],
        "cardIds": ids,
    }


def seed(db):
    db.board_snapshots.delete_many({})
    ids1 = {"backlog": [5001, 5002], "todo": [5003], "in_progress": [], "done": [5005]}
    ids2 = {"backlog": [5001], "todo": [5002], "in_progress": [5003], "done": [5005]}
    db.board_snapshots.insert_many(
        [
            snap(datetime(2026, 10, 1, 8, tzinfo=UTC), ids1, {2001: [5001, 5002], 2002: [5003], 2005: [5005]}),
            snap(datetime(2026, 10, 1, 18, tzinfo=UTC), ids2, {2001: [5001], 2002: [5002], 2003: [5003], 2005: [5005]}),
            # 23:30 UTC = 00:30 de 2 de outubro em Lisboa
            snap(datetime(2026, 10, 1, 23, 30, tzinfo=UTC), ids2 | {"done": [5005, 5006]}, {2003: [5003], 2005: [5005, 5006]}),
            snap(datetime(2026, 11, 5, tzinfo=UTC), ids2, {}),
        ]
    )


def test_last_snapshot_per_local_day_by_status(synced, db):
    seed(db)
    body = synced.get(URL, params=PERIOD).json()
    assert body["available"] and body["filtered"] is False
    assert [s["key"] for s in body["series"]] == ["backlog", "todo", "in_progress", "done"]
    assert [d["date"] for d in body["days"]] == ["2026-10-01", "2026-10-02"]
    assert body["days"][0]["counts"] == {"backlog": 1, "todo": 1, "in_progress": 1, "done": 1}
    assert body["days"][1]["counts"]["done"] == 2
    assert body["snapshotsSince"].startswith("2026-10-01T08:00")


def test_by_column_follows_board_order_and_filters_use_card_ids(synced, db):
    seed(db)
    body = synced.get(URL, params=PERIOD | {"group": "column"}).json()
    order = [c["columnId"] for c in db.boards.find_one({"boardId": 96})["structure"]["columns"]]
    keys = [int(s["key"]) for s in body["series"]]
    assert keys == sorted(keys, key=order.index) and set(keys) == {2001, 2002, 2003, 2005}
    assert all(s["label"] and not s["label"].startswith("Coluna") for s in body["series"])
    assert body["days"][0]["counts"] == {"2001": 1, "2002": 1, "2003": 1, "2005": 1}
    assert body["days"][1]["counts"]["2001"] == 0

    # Ana (11) é responsável pelos cartões 5002 e 5004
    filtered = synced.get(URL, params=PERIOD | {"ownerUserId": 11}).json()
    assert filtered["filtered"] is True
    assert filtered["days"][0]["counts"] == {"backlog": 0, "todo": 1, "in_progress": 0, "done": 0}


def test_sync_snapshot_keeps_card_ids_per_column(synced, db):
    entries = db.board_snapshots.find_one({"boardId": 96})["byColumn"]
    assert all(len(e["cardIds"]) == e["count"] for e in entries)
    assert synced.get(URL).json()["available"] is True


def test_unavailable_reasons_and_validation(synced, db):
    assert synced.get(URL, params={"from": "2025-01-01", "to": "2025-01-31"}).json()["reason"] == "sem snapshots no período"
    db.board_snapshots.delete_many({})
    body = synced.get(URL).json()
    assert body["available"] is False and body["reason"] == "recolha de histórico ainda não iniciada"
    assert synced.get(URL, params={"group": "lane"}).status_code == 422
    assert synced.get("/api/v1/boards/999/cfd").status_code == 404
