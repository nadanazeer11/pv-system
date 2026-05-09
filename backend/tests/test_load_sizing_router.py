"""Tests for the /api/load-sizing endpoint."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_appliance_library_endpoint_returns_seeded_entries():
    response = client.get("/api/load-sizing/library")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 10
    sample = body[0]
    assert {"name", "watts", "typical_hours_per_day", "category"} <= set(sample.keys())


def test_size_from_load_happy_path():
    response = client.post(
        "/api/load-sizing",
        json={
            "appliances": [
                {"name": "AC", "watts": 1500, "hours_per_day": 6, "quantity": 1},
                {"name": "Fridge", "watts": 150, "hours_per_day": 10, "quantity": 1},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    # 1500*6 + 150*10 = 9000 + 1500 = 10500 Wh = 10.5 kWh/day
    assert body["daily_load_kwh"] == 10.5
    assert body["peak_load_kw"] == 1.65
    assert body["recommended_panel_count"] >= 1
    assert body["recommended_system_kw"] > 0
    assert body["required_roof_area_m2"] > 0
    assert body["roof_fits"] is None


def test_size_from_load_with_roof_area_reports_fit():
    response = client.post(
        "/api/load-sizing",
        json={
            "appliances": [
                {"name": "x", "watts": 500, "hours_per_day": 2, "quantity": 1}
            ],
            "available_roof_area_m2": 10_000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["roof_fits"] is True
    assert body["available_roof_area_m2"] == 10_000


def test_size_from_load_with_undersized_roof():
    response = client.post(
        "/api/load-sizing",
        json={
            "appliances": [
                {"name": "AC", "watts": 2200, "hours_per_day": 8, "quantity": 4}
            ],
            "available_roof_area_m2": 5.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["roof_fits"] is False
    assert body["roof_area_shortfall_m2"] > 0


def test_size_from_load_validates_empty_list():
    response = client.post("/api/load-sizing", json={"appliances": []})
    assert response.status_code == 422


def test_size_from_load_returns_422_for_zero_load():
    response = client.post(
        "/api/load-sizing",
        json={
            "appliances": [
                {"name": "x", "watts": 1000, "hours_per_day": 0, "quantity": 1}
            ],
        },
    )
    assert response.status_code == 422
    assert "zero" in response.json()["detail"].lower()
