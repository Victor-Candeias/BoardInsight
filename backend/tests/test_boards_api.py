import asyncio

from app.services.sync import SyncService


def test_add_board_validates_via_api_and_enqueues_sync(client, db):
    response = client.post("/api/v1/boards", json={"boardId": 96})
    assert response.status_code == 201
    board = response.json()
    assert board["name"] == "Team Board: Exemplo" and board["enabled"] is True and board["stale"] is True
    assert db.jobs.find_one({"type": "sync_board"})["payload"] == {"boardId": 96}
    assert client.post("/api/v1/boards", json={"boardId": 96}).json()["error"]["code"] == "board_exists"


def test_add_unknown_board_returns_404_without_saving(client, db):
    response = client.post("/api/v1/boards", json={"boardId": 12345})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "businessmap_not_found"
    assert db.boards.count_documents({}) == 0


def test_add_board_rejects_invalid_id(client):
    assert client.post("/api/v1/boards", json={"boardId": 0}).status_code == 422


def test_list_search_and_detail_with_column_mapping(client):
    client.post("/api/v1/boards", json={"boardId": 96})
    assert [b["boardId"] for b in client.get("/api/v1/boards").json()] == [96]
    assert client.get("/api/v1/boards", params={"search": "exemplo"}).json()[0]["boardId"] == 96
    assert client.get("/api/v1/boards", params={"search": "96"}).json()[0]["boardId"] == 96
    assert client.get("/api/v1/boards", params={"search": "xyz"}).json() == []
    detail = client.get("/api/v1/boards/96").json()
    columns = {c["columnId"]: c for c in detail["columns"]}
    assert columns[2003]["status"] == "in_progress" and columns[2003]["cycleTime"] is True
    assert columns[2001]["sectionName"] == "Backlog" and columns[2001]["cycleTime"] is False
    assert {lane["laneId"] for lane in detail["lanes"]} == {3001, 3002}


def test_patch_enabled_and_delete_removes_data(client, db, settings, client_factory):
    client.post("/api/v1/boards", json={"boardId": 96})
    assert client.patch("/api/v1/boards/96", json={"enabled": False}).json()["enabled"] is False
    asyncio.run(SyncService(db, settings, client_factory).sync_board(96))
    assert db.cards.count_documents({"boardId": 96}) == 7
    assert client.delete("/api/v1/boards/96").status_code == 204
    assert db.cards.count_documents({}) == 0 and db.sync_runs.count_documents({}) == 0
    assert db.jobs.count_documents({"status": "pending"}) == 0
    assert client.get("/api/v1/boards/96").status_code == 404


def test_test_connection_reports_each_resource(client, fake_bm):
    fake_bm.fail(r"/users", 403)
    result = client.post("/api/v1/boards/96/test-connection").json()
    checks = {c["name"]: c for c in result["checks"]}
    assert result["ok"] is True and result["boardName"] == "Team Board: Exemplo"
    assert checks["cards"]["ok"] is True
    assert checks["users"] == {**checks["users"], "ok": False, "code": "permission_denied", "required": False}
    assert result["rateLimit"]["perMinuteRemaining"] == 29


def test_test_connection_fails_when_cards_not_readable(client, fake_bm):
    fake_bm.fail(r"/cards", 403)
    result = client.post("/api/v1/boards/96/test-connection").json()
    assert result["ok"] is False


def test_test_connection_unknown_board(client):
    result = client.post("/api/v1/boards/777/test-connection").json()
    assert result["ok"] is False and [c["name"] for c in result["checks"]] == ["board"]


def test_sync_runs_history(client, db, settings, client_factory):
    client.post("/api/v1/boards", json={"boardId": 96})
    asyncio.run(SyncService(db, settings, client_factory).sync_board(96, trigger="manual"))
    runs = client.get("/api/v1/boards/96/sync-runs").json()
    assert len(runs) == 1 and runs[0]["status"] == "success" and runs[0]["trigger"] == "manual"
