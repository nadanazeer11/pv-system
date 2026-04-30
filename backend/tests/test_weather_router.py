"""Tests for the /api/weather/tmy endpoint."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import pvgis_service

client = TestClient(app)

CAIRO = {"latitude": 30.0444, "longitude": 31.2357}


def test_get_tmy_summary_happy_path(fake_tmy):
    async def fake_fetch(lat, lon):
        return fake_tmy

    with patch.object(pvgis_service, "fetch_tmy", side_effect=fake_fetch):
        response = client.post("/api/weather/tmy", json=CAIRO)

    assert response.status_code == 200
    body = response.json()
    assert body["location"] == CAIRO
    assert body["summary"]["hours_count"] == 8760
    assert body["summary"]["annual_ghi_kwh_per_m2"] > 0


def test_get_tmy_summary_propagates_pvgis_error():
    async def boom(lat, lon):
        raise pvgis_service.PVGISError("upstream is down")

    with patch.object(pvgis_service, "fetch_tmy", side_effect=boom):
        response = client.post("/api/weather/tmy", json=CAIRO)

    assert response.status_code == 502
    assert "upstream is down" in response.json()["detail"]


def test_get_tmy_summary_validates_location():
    response = client.post(
        "/api/weather/tmy",
        json={"latitude": 999, "longitude": 0},
    )
    assert response.status_code == 422
