from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "PV Rooftop Solar Estimator"
    assert body["version"] == "0.1.0"
