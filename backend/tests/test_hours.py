import asyncio
from datetime import datetime, timedelta

import pytest

URL = "/api/v1/boards/96/hours"


def entry(lid, user, card, column, days_ago, seconds, *, subtask=None, lane=3001, logged_days_ago=None, today):
    day = today - timedelta(days=days_ago)
    logged = today - timedelta(days=days_ago if logged_days_ago is None else logged_days_ago)
    return {
        "logged_time_id": lid,
        "parent_card_id": 0,
        "card_id": card,
        "subtask_id": subtask,
        "lane_id": lane,
        "column_id": column,
        "user_id": user,
        "category_id": 0,
        "date": day.isoformat(),
        "time": seconds,
        "comment": f"registo {lid}",
        "logged_at": f"{logged.isoformat()}T18:00:00+01:00",
    }


@pytest.fixture
def today(settings):
    return datetime.now(settings.tz).date()


@pytest.fixture
def board(client, fake_bm, today):
    fake_bm.logged_times = [
        entry(1, 11, 5001, 2001, 2, 3600, today=today),
        entry(2, 11, 5002, 2002, 2, 1800, subtask=77, today=today),
        entry(3, 12, 5004, 2004, 10, 6000, today=today),
        entry(4, 11, 9999, 9001, 2, 7200, lane=9002, today=today),  # outro board
        entry(5, 13, 777, 2003, 40, 900, today=today),  # cartão fora da BD mas coluna do board
    ]
    client.post("/api/v1/boards", json={"boardId": 96})
    return client


def sync(db, settings, client_factory):
    from app.services.sync import SyncService

    return asyncio.run(SyncService(db, settings, client_factory).sync_board(96))


def logged_requests(fake_bm):
    return [r.url.params for r in fake_bm.requests if r.url.path.endswith("/loggedTime")]


def test_sync_keeps_only_board_entries_and_reconciles_window(board, db, settings, client_factory, fake_bm, today):
    result = sync(db, settings, client_factory)
    assert result.status == "success" and result.stats["loggedTimeEntries"] == 4
    assert sorted(d["loggedTimeId"] for d in db.logged_times.find()) == [1, 2, 3, 5]
    first = logged_requests(fake_bm)
    assert len(first) == 1  # primeira recolha: só a janela da retenção
    assert first[0]["include_logged_time_for_subtasks"] == "1"
    assert first[0]["from_date"] == (today - timedelta(days=settings.retention_history_days)).isoformat()
    assert db.boards.find_one({"boardId": 96})["loggedTimeSyncedAt"] is not None

    fake_bm.requests.clear()
    fake_bm.logged_times[0]["time"] = 4500  # editado
    del fake_bm.logged_times[2]  # apagado no Businessmap
    fake_bm.logged_times.append(entry(6, 12, 5003, 2003, 100, 600, logged_days_ago=0, today=today))  # data antiga, registo novo
    result = sync(db, settings, client_factory)
    assert result.stats["loggedTimeRemoved"] == 1
    docs = {d["loggedTimeId"]: d for d in db.logged_times.find()}
    assert sorted(docs) == [1, 2, 5, 6] and docs[1]["seconds"] == 4500 and docs[2]["subtaskId"] == 77
    window, recent = logged_requests(fake_bm)
    assert window["from_date"] == (today - timedelta(days=settings.logged_time_sync_days)).isoformat()
    assert recent["logged_from_date"] == (today - timedelta(days=1)).isoformat()


def test_logged_time_failure_does_not_fail_sync(board, db, settings, client_factory, fake_bm):
    fake_bm.fail(r"/loggedTime", 403)
    result = sync(db, settings, client_factory)
    assert result.status == "success"
    assert any("tempo registado" in w for w in result.stats["warnings"])
    stored = db.boards.find_one({"boardId": 96})
    assert stored["loggedTimeError"]["code"] == "permission_denied" and "loggedTimeSyncedAt" not in stored
    body = board.get(URL).json()
    assert body["available"] is False and "falhou" in body["warning"]


def test_hours_report_by_user_period_and_subtasks(board, db, settings, client_factory, today):
    sync(db, settings, client_factory)
    params = {"from": (today - timedelta(days=14)).isoformat(), "to": today.isoformat(), "granularity": "day"}
    body = board.get(URL, params=params).json()
    assert body["available"] is True and body["warning"] is None
    assert (body["totalSeconds"], body["entryCount"], body["cardCount"], body["peopleCount"]) == (11400, 3, 3, 2)
    assert [u["userId"] for u in body["users"]] == [11, 12, 13]
    rows = {r["userId"]: r for r in body["byUser"]}
    assert [r["userId"] for r in body["byUser"]] == [12, 11]  # mais horas primeiro
    assert (rows[11]["seconds"], rows[11]["entries"], rows[11]["cards"], rows[11]["days"]) == (5400, 2, 2, 1)
    assert len(rows[11]["series"]) == 15 and rows[11]["series"][-3] == 5400
    first = body["entries"][0]
    assert first["date"] == (today - timedelta(days=2)).isoformat() and first["customId"] in ("T-5001", "T-5002")
    assert {e["loggedTimeId"]: e["subtask"] for e in body["entries"]} == {2: True, 1: False, 3: False}

    only_ana = board.get(URL, params={**params, "userId": 11, "includeSubtasks": "false"}).json()
    assert (only_ana["totalSeconds"], only_ana["userId"], only_ana["includeSubtasks"]) == (3600, 11, False)
    assert [e["loggedTimeId"] for e in only_ana["entries"]] == [1]

    older = board.get(URL, params={"from": (today - timedelta(days=60)).isoformat(), "to": today.isoformat()}).json()
    assert older["totalSeconds"] == 12300
    assert board.get("/api/v1/boards/1/hours").status_code == 404
