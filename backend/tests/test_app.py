def test_version_endpoint(client):
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["name"] == "BoardInsight"


def test_openapi_is_served_under_api_prefix(client):
    assert client.get("/api/openapi.json").status_code == 200


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_when_mongo_and_key_ok(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_not_ready_without_api_key(client, settings):
    settings.businessmap_api_key = None
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["businessmap_api_key"]["ok"] is False
