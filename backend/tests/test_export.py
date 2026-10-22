import csv
import io
import json

URL = "/api/v1/boards/96/cards/export"


def test_csv_uses_semicolons_bom_local_time_and_decimal_comma(synced, db):
    db.cards.update_one({"cardId": 5001}, {"$set": {"title": "=HYPERLINK(\"http://x\")"}})
    resp = synced.get(URL, params={"sort": "cardId"})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"].startswith('attachment; filename="boardinsight-board96-cartoes-')
    text = resp.content.decode("utf-8")
    assert text.startswith("\ufeffID;ID personalizado;Título;")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"))
    assert [r["ID"] for r in rows] == ["5001", "5002", "5003", "5004", "5005", "5006"] and resp.headers["x-total-count"] == "6"
    by_id = {r["ID"]: r for r in rows}
    assert by_id["5001"]["Título"].startswith("'=HYPERLINK")
    assert by_id["5003"]["Bloqueado"] == "Sim" and by_id["5002"]["Bloqueado"] == "Não"
    # 5006: início 22/09 09:00 UTC, fim 30/09 12:00 UTC → 8,125 dias; Lisboa = UTC+1 no verão
    assert by_id["5006"]["Cycle time (dias)"] == "8,12"
    assert by_id["5006"]["Fim"] == "2026-09-30 13:00"
    assert by_id["5003"]["Idade em curso (dias)"] != "" and by_id["5005"]["Idade em curso (dias)"] == ""


def test_json_respects_filters_and_sort(synced):
    resp = synced.get(URL, params={"format": "json", "ownerUserId": 11, "sort": "-cardId"})
    body = json.loads(resp.content)
    assert resp.headers["content-type"] == "application/json"
    assert body["boardId"] == 96 and body["total"] == 2
    assert [i["cardId"] for i in body["items"]] == [5004, 5002]
    item = body["items"][1]
    assert item["status"] == "A fazer" and item["overdue"] is True and item["deadline"].startswith("2026-10-10")


def test_export_limits_and_validation(synced, settings):
    settings.export_max_rows = 3
    resp = synced.get(URL)
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "export_too_large"
    assert synced.get(URL, params={"format": "xml"}).status_code == 422
    assert synced.get(URL, params={"sort": "nope"}).status_code == 422
    assert synced.get("/api/v1/boards/999/cards/export").status_code == 404
