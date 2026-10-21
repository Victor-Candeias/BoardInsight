from datetime import UTC, datetime

import pytest

from app.services.flow import percentile

URL = "/api/v1/boards/96/flow"
PERIOD = {"from": "2026-08-01", "to": "2026-10-31", "granularity": "month"}


def days(a, b):
    return (b - a).total_seconds() / 86400


def test_percentile_uses_linear_interpolation():
    assert percentile([4, 1, 3, 2], 50) == 2.5
    assert percentile([1, 2, 3, 4], 85) == pytest.approx(3.55)
    assert percentile([7], 95) == 7


def test_lead_and_cycle_time_percentiles(synced):
    body = synced.get(URL, params=PERIOD).json()
    d = lambda *a: datetime(*a, tzinfo=UTC)  # noqa: E731
    cycle = sorted(
        [days(d(2026, 8, 5, 9), d(2026, 8, 20, 10)), days(d(2026, 9, 15, 9), d(2026, 10, 5, 16)), days(d(2026, 9, 22, 9), d(2026, 9, 30, 12))]
    )
    ct = body["cycleTime"]
    assert ct["available"] and ct["count"] == 3 and ct["smallSample"] is True and ct["withoutStart"] == 0
    assert ct["p50"] == pytest.approx(cycle[1], abs=0.01)
    assert ct["p85"] == pytest.approx(cycle[1] + 0.7 * (cycle[2] - cycle[1]), abs=0.01)
    assert body["leadTime"]["max"] == pytest.approx(days(d(2026, 9, 5, 8), d(2026, 10, 5, 16)), abs=0.01)
    assert [t["count"] for t in body["trend"]] == [1, 1, 1]
    assert {p["cardId"] for p in body["points"]} == {4001, 5005, 5006}


def test_wip_and_aging_against_cycle_time_p85(synced):
    body = synced.get(URL, params=PERIOD).json()
    wip = body["wip"]
    assert (wip["total"], wip["blocked"]) == (2, 1)
    assert [c["key"] for c in wip["byColumn"]] == [2003, 2004]
    aging = body["aging"]
    assert [a["cardId"] for a in aging["items"]] == [5003, 5004]  # mais antigo primeiro
    assert aging["threshold"] == body["cycleTime"]["p85"]
    assert aging["aboveThreshold"] == sum(a["ageDays"] > aging["threshold"] for a in aging["items"])
    assert aging["items"][0]["isBlocked"] is True and aging["items"][0]["estimated"] is False


def test_unavailable_metrics_have_reason(synced):
    body = synced.get(URL, params={"from": "2025-01-01", "to": "2025-01-31"}).json()
    assert body["leadTime"] == {"available": False, "reason": "sem cartões concluídos no período", "count": 0}
    assert body["cycleTime"]["available"] is False
    assert body["aging"]["threshold"] is None and body["aging"]["aboveThreshold"] == 0
    assert synced.get(URL, params={"ownerUserId": 13}).json()["wip"]["total"] == 0
