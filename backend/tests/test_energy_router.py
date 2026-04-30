"""Tests for the /api/energy/pvlib endpoint.

PVGIS is patched so the router never reaches the network. We assert the
endpoint correctly orchestrates fetch-TMY → simulate, surfaces service
errors as the right HTTP codes, and echoes assumptions in the response.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import pvgis_service

client = TestClient(app)


def _patch_fetch_tmy(fake_tmy):
    """Helper: patch pvgis_service.fetch_tmy to return our fixture."""
    async def _async_fake(latitude, longitude):  # noqa: ARG001
        return fake_tmy

    return patch.object(pvgis_service, "fetch_tmy", side_effect=_async_fake)


def test_pvlib_endpoint_happy_path(fake_tmy):
    with _patch_fetch_tmy(fake_tmy):
        response = client.post(
            "/api/energy/pvlib",
            json={
                "location": {"latitude": 30.0, "longitude": 31.2},
                "system_kw": 5.0,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["monthly_kwh"]) == 12
    assert body["annual_kwh"] > 0
    assert body["system_kw"] == 5.0
    # Echoed Egypt-tuned defaults
    assert body["tilt_deg"] == settings.default_tilt_deg
    assert body["azimuth_deg"] == settings.default_azimuth_deg
    assert body["inverter_efficiency"] == settings.inverter_efficiency


def test_pvlib_endpoint_honours_overrides(fake_tmy):
    with _patch_fetch_tmy(fake_tmy):
        response = client.post(
            "/api/energy/pvlib",
            json={
                "location": {"latitude": 30.0, "longitude": 31.2},
                "system_kw": 5.0,
                "tilt_deg": 15.0,
                "azimuth_deg": 200.0,
                "inverter_efficiency": 0.95,
                "system_losses_fraction": 0.10,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["tilt_deg"] == 15.0
    assert body["azimuth_deg"] == 200.0
    assert body["inverter_efficiency"] == 0.95
    assert body["system_losses_fraction"] == 0.10


def test_pvlib_endpoint_502_on_pvgis_failure():
    """If PVGIS is down, the user sees an actionable 502, not a 500."""
    async def _boom(latitude, longitude):  # noqa: ARG001
        raise pvgis_service.PVGISError("PVGIS unreachable")

    with patch.object(pvgis_service, "fetch_tmy", side_effect=_boom):
        response = client.post(
            "/api/energy/pvlib",
            json={
                "location": {"latitude": 30.0, "longitude": 31.2},
                "system_kw": 5.0,
            },
        )

    assert response.status_code == 502
    assert "PVGIS unreachable" in response.json()["detail"]


def test_pvlib_endpoint_validates_system_kw():
    """Pydantic must reject system_kw <= 0 at the schema layer."""
    response = client.post(
        "/api/energy/pvlib",
        json={
            "location": {"latitude": 30.0, "longitude": 31.2},
            "system_kw": 0,
        },
    )
    assert response.status_code == 422
