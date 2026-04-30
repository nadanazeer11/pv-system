"""Tests for the /api/sizing endpoint."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_size_system_happy_path():
    response = client.post("/api/sizing", json={"roof_area_m2": 100.0})

    assert response.status_code == 200
    body = response.json()
    assert body["panel_count"] == 38
    assert body["system_kw"] == 17.1
    assert body["usable_roof_area_m2"] == 70.0
    # Echoed defaults
    assert body["panel_rated_watts"] == 450.0
    assert body["panel_area_m2"] == 1.8
    assert body["roof_utilization_factor"] == 0.7


def test_size_system_with_overrides():
    response = client.post(
        "/api/sizing",
        json={
            "roof_area_m2": 200.0,
            "panel_rated_watts": 600.0,
            "panel_area_m2": 2.4,
            "roof_utilization_factor": 0.5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["panel_count"] == 41
    assert body["panel_rated_watts"] == 600.0


def test_size_system_validates_positive_area():
    response = client.post("/api/sizing", json={"roof_area_m2": 0})
    assert response.status_code == 422


def test_size_system_returns_422_for_too_small_roof():
    """Service-level SizingError surfaces as HTTP 422 with a clear
    explanation, not a 500."""
    response = client.post("/api/sizing", json={"roof_area_m2": 2.0})

    assert response.status_code == 422
    assert "smaller than a single panel" in response.json()["detail"]
