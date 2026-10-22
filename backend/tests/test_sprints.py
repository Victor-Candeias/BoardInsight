from datetime import UTC, date, datetime

from app.services.sprints import list_sprints

URL = "/api/v1/boards/96/sprints"
CONFIG = {
    "cadence": None,
    "explicit": [
        {"name": "S2", "start": "2026-10-06", "end": "2026-10-19"},
        {"name": "S1", "start": "2026-09-28", "end": "2026-10-05"},
        {"name": "S3", "start": "2026-12-01", "end": "2026-12-14"},
    ],
}


def snap(at, **ids):
    return {"boardId": 96, "capturedAt": at, "cardIds": {s: ids.get(s, []) for s in ("backlog", "todo", "in_progress", "done")}}


def seed(db):
    db.board_snapshots.insert_many(
        [
            snap(datetime(2026, 9, 28, 8, tzinfo=UTC), todo=[5002, 5003], in_progress=[5005, 5006]),
            snap(datetime(2026, 9, 28, 20, tzinfo=UTC), todo=[5002, 5003], in_progress=[5005, 5006]),
            snap(datetime(2026, 9, 30, 13, tzinfo=UTC), todo=[5002], in_progress=[5003, 5004, 5005], done=[5006]),
            snap(datetime(2026, 10, 4, 20, tzinfo=UTC), todo=[5002], in_progress=[5003, 5004], done=[5005, 5006]),
        ]
    )


def test_cadence_generates_sprints_up_to_today():
    config = {"cadence": {"start": "2026-09-07", "lengthDays": 14, "namePrefix": "Sprint"}, "explicit": []}
    sprints = list_sprints(config, date(2026, 10, 21))
    assert [(s["name"], s["start"].isoformat(), s["end"].isoformat(), s["state"]) for s in sprints] == [
        ("Sprint 1", "2026-09-07", "2026-09-20", "past"),
        ("Sprint 2", "2026-09-21", "2026-10-04", "past"),
        ("Sprint 3", "2026-10-05", "2026-10-18", "past"),
        ("Sprint 4", "2026-10-19", "2026-11-01", "current"),
    ]
    assert list_sprints(config, date(2026, 9, 1)) == []
    # A lista explícita prevalece sobre a cadência.
    assert [s["name"] for s in list_sprints(config | {"explicit": CONFIG["explicit"]}, date(2026, 10, 21))] == ["S1", "S2", "S3"]


def test_config_validation(synced):
    assert synced.put(f"{URL}/config", json=CONFIG).json()["explicit"][0]["name"] == "S2"
    assert synced.get("/api/v1/boards/96").json()["sprints"]["explicit"][1]["start"] == "2026-09-28"
    overlap = CONFIG["explicit"] + [{"name": "X", "start": "2026-10-19", "end": "2026-10-20"}]
    assert synced.put(f"{URL}/config", json={"explicit": overlap}).status_code == 422
    assert synced.put(f"{URL}/config", json={"explicit": [{"name": "X", "start": "2026-10-02", "end": "2026-10-01"}]}).status_code == 422
    assert synced.put(f"{URL}/config", json={"cadence": {"start": "2026-10-01", "lengthDays": 0}}).status_code == 422


def test_velocity_and_commitment_per_sprint(synced, db):
    seed(db)
    synced.put(f"{URL}/config", json=CONFIG)
    body = synced.get(URL).json()
    rows = {r["name"]: r for r in body["sprints"]}
    assert list(rows) == ["S1", "S2"] and body["upcoming"][0]["name"] == "S3"
    s1 = rows["S1"]
    assert (s1["completed"], s1["completedSize"], s1["committed"], s1["committedDone"], s1["completionRate"]) == (2, 9, 4, 2, 0.5)
    assert rows["S2"]["commitmentAvailable"] is False and rows["S2"]["commitmentReason"] == "sem snapshot no primeiro dia da sprint"
    assert (body["averageVelocity"], body["averageVelocitySprints"]) == (1.0, 2)


def test_burndown_and_scope_added(synced, db):
    seed(db)
    synced.put(f"{URL}/config", json=CONFIG)
    body = synced.get(f"{URL}/2026-09-28").json()
    burndown = {d["date"]: d for d in body["burndown"]}
    assert len(burndown) == 8
    assert [burndown[d]["remaining"] for d in ("2026-09-28", "2026-09-29", "2026-09-30", "2026-10-04")] == [4, None, 3, 2]
    assert burndown["2026-09-28"]["remainingSize"] == 14 and burndown["2026-09-28"]["ideal"] == 4
    assert burndown["2026-10-05"]["ideal"] == 0
    assert [a["cardId"] for a in body["added"]] == [5004]
    assert [(c["cardId"], c["doneInSprint"]) for c in body["commitment"]] == [(5002, False), (5003, False), (5005, True), (5006, True)]

    mine = synced.get(f"{URL}/2026-09-28", params={"ownerUserId": 12}).json()
    assert (mine["committed"], mine["completed"], mine["added"]) == (2, 1, [])
    assert synced.get(f"{URL}/2026-01-01").status_code == 404
