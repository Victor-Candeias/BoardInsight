from fastapi.testclient import TestClient

from app.main import create_app


def test_version_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["name"] == "BoardInsight"


def test_openapi_is_served_under_api_prefix():
    client = TestClient(create_app())
    assert client.get("/api/openapi.json").status_code == 200
