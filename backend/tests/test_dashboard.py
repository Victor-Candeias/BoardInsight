URL = "/api/v1/boards/96/dashboard"
PERIOD = {"from": "2026-08-01", "to": "2026-10-31", "granularity": "month"}


def test_dashboard_kpis_distributions_and_timeline(synced):
    body = synced.get(URL, params=PERIOD).json()
    k = body["kpis"]
    assert (k["total"], k["backlog"], k["todo"], k["inProgress"], k["active"], k["done"]) == (6, 1, 1, 2, 3, 2)
    assert (k["blocked"], k["unassigned"], k["overdue"]) == (1, 1, 1)
    assert (k["createdInPeriod"], k["completedInPeriod"]) == (7, 3)
    assert [(t["label"], t["created"], t["completed"]) for t in body["timeline"]] == [
        ("ago 2026", 1, 1),
        ("set 2026", 6, 1),
        ("out 2026", 0, 1),
    ]
    status = {d["key"]: d["count"] for d in body["distributions"]["status"]}
    assert status == {"backlog": 1, "todo": 1, "in_progress": 2, "done": 2}
    assert [d["key"] for d in body["distributions"]["status"]] == ["backlog", "todo", "in_progress", "done"]
    owners = {d["label"]: d["count"] for d in body["distributions"]["owner"]}
    assert owners["Sem responsável"] == 1 and sum(owners.values()) == 6
    assert body["distributions"]["priority"][0] == {"key": 1, "label": "Crítica", "count": 1}
    assert body["stale"] is False and body["dataAsOf"]


def test_dashboard_filters_apply_to_kpis_and_timeline(synced):
    body = synced.get(URL, params={**PERIOD, "ownerUserId": 12}).json()
    assert body["kpis"]["total"] == 2 and body["kpis"]["completedInPeriod"] == 1
    body = synced.get(URL, params={**PERIOD, "status": "done"}).json()
    assert body["kpis"]["total"] == 2 and body["kpis"]["completedInPeriod"] == 3


def test_weekly_buckets_are_iso_weeks_in_local_time(synced):
    body = synced.get(URL, params={"from": "2026-09-28", "to": "2026-10-11", "granularity": "week"}).json()
    assert [(t["bucket"], t["label"], t["completed"]) for t in body["timeline"]] == [
        ("2026-09-28", "2026-S40", 1),
        ("2026-10-05", "2026-S41", 1),
    ]


def test_dashboard_default_period_and_validation(synced):
    body = synced.get(URL).json()
    assert body["period"]["granularity"] == "week" and len(body["timeline"]) in (12, 13)
    assert synced.get(URL, params={"from": "2026-10-01", "to": "2026-09-01"}).status_code == 422
    assert synced.get(URL, params={"from": "2020-01-01", "to": "2026-01-01", "granularity": "day"}).status_code == 422
