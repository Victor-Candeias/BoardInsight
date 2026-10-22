from datetime import UTC, datetime, timedelta

URL = "/api/v1/boards/96/attention"
PERIOD = {"from": "2026-08-01", "to": "2026-10-31"}


def test_attention_reasons_order_and_wip(synced, db, settings):
    settings.attention_wip_per_person = 1
    db.cards.update_one({"cardId": 5001}, {"$set": {"status": "todo"}})
    db.cards.update_one({"cardId": 5002}, {"$set": {"status": "in_progress", "firstStartTime": datetime.now(UTC) - timedelta(days=1)}})
    db.cards.update_one({"cardId": 5004}, {"$set": {"deadline": datetime.now(UTC) + timedelta(days=2)}})
    body = synced.get(URL, params=PERIOD).json()

    # P85 do cycle time de 4001, 5005 e 5006 (8,1 / 15,0 / 20,3 dias).
    ref = body["agingReference"]
    assert ref["count"] == 3 and ref["smallSample"] is True and 18 < ref["p85"] < 19.5

    reasons = {i["cardId"]: i["reasons"] for i in body["items"]}
    assert reasons == {
        5003: ["blocked", "aging"],
        5002: ["overdue"],
        5004: ["aging", "dueSoon"],
        5001: ["unassigned"],
    }
    assert [i["cardId"] for i in body["items"]] == [5003, 5002, 5004, 5001]
    assert body["summary"] | {"reopenedCards": 0} == {
        "blocked": 1,
        "overdue": 1,
        "aging": 2,
        "dueSoon": 1,
        "unassigned": 1,
        "wipOverLimit": 1,
        "reopenedCards": 0,
    }
    assert body["people"] == [{"userId": 11, "name": "Utilizador A", "inProgress": 2}]
    assert body["wipLimit"] == 1 and body["openTotal"] == 4 and body["total"] == 4


def test_attention_without_completed_cards_has_no_aging(synced):
    body = synced.get(URL, params={"from": "2026-01-01", "to": "2026-01-31"}).json()
    assert body["agingReference"]["p85"] is None
    assert body["summary"]["aging"] == 0
    assert synced.get("/api/v1/boards/1/attention").status_code == 404
