"""HTTP-shape tests for the roof detection endpoints.

Service-level behaviour is covered by ``test_roof_detection``; these
tests verify only the FastAPI surface — error mapping, response shape,
and config-aware degradation for the satellite-tile endpoint.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.inputs import Location
from app.schemas.roof import RoofDetectionResult
from app.services import gmaps_static, overpass_service, roof_detection

client = TestClient(app)


def _square(lat: float, lng: float, h: float = 0.0001) -> list[tuple[float, float]]:
    return [
        (lat - h, lng - h),
        (lat - h, lng + h),
        (lat + h, lng + h),
        (lat + h, lng - h),
        (lat - h, lng - h),
    ]


# ────────────────────────────────────────────────────────────────────
# /api/roof/detect
# ────────────────────────────────────────────────────────────────────
def test_detect_happy_path(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "")
    raw = [
        {
            "osm_way_id": 42,
            "coordinates_lat_lng": _square(30.0444, 31.2357),
            "tags": {"building": "yes", "building:levels": "4"},
        }
    ]
    with patch.object(overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)):
        response = client.post(
            "/api/roof/detect",
            json={"location": {"latitude": 30.0444, "longitude": 31.2357}},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["primary_roof"]["osm_way_id"] == 42
    assert body["primary_roof"]["contains_query_point"] is True
    assert body["primary_roof"]["tags"]["building:levels"] == "4"
    assert body["search_radius_m"] > 0
    assert body["detection_source"] == "osm-overpass"


def test_detect_empty_returns_200_with_null_primary(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "")
    with patch.object(overpass_service, "fetch_buildings", new=AsyncMock(return_value=[])):
        response = client.post(
            "/api/roof/detect",
            json={"location": {"latitude": 30.0444, "longitude": 31.2357}},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["primary_roof"] is None
    assert body["candidates"] == []
    assert any("No OSM building" in n for n in body["notes"])


def test_detect_overpass_failure_becomes_502(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    with patch.object(
        overpass_service,
        "fetch_buildings",
        new=AsyncMock(side_effect=overpass_service.OverpassError("502 from upstream")),
    ):
        response = client.post(
            "/api/roof/detect",
            json={"location": {"latitude": 30.0444, "longitude": 31.2357}},
        )
    assert response.status_code == 502
    assert "OSM Overpass fetch failed" in response.json()["detail"]


def test_detect_rejects_invalid_radius():
    response = client.post(
        "/api/roof/detect",
        json={
            "location": {"latitude": 30.0, "longitude": 31.0},
            "search_radius_m": -1.0,
        },
    )
    assert response.status_code == 422


def test_detect_rejects_invalid_latitude():
    response = client.post(
        "/api/roof/detect",
        json={"location": {"latitude": 95.0, "longitude": 31.0}},
    )
    assert response.status_code == 422


# ────────────────────────────────────────────────────────────────────
# /api/roof/satellite-tile
# ────────────────────────────────────────────────────────────────────
def test_satellite_tile_happy_path(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "TILE-KEY")
    response = client.post(
        "/api/roof/satellite-tile",
        json={
            "location": {"latitude": 30.0444, "longitude": 31.2357},
            "zoom": 20,
            "size_px": 640,
            "scale": 2,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["zoom"] == 20
    assert body["size_px"] == 640
    assert body["scale"] == 2
    assert body["meters_per_pixel"] > 0
    assert body["tile_width_m"] == pytest.approx(body["meters_per_pixel"] * 640 * 2, rel=1e-9)
    assert "key=TILE-KEY" in body["url"]
    assert "maps.googleapis.com" in body["url"]


def test_satellite_tile_missing_key_returns_503(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "")
    response = client.post(
        "/api/roof/satellite-tile",
        json={"location": {"latitude": 30.0, "longitude": 31.0}},
    )
    assert response.status_code == 503
    assert "GOOGLE_MAPS_API_KEY" in response.json()["detail"]


def test_satellite_tile_uses_defaults_when_unspecified(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "gmaps_static_default_zoom", 19)
    monkeypatch.setattr(gmaps_static.settings, "gmaps_static_default_size_px", 320)
    monkeypatch.setattr(gmaps_static.settings, "gmaps_static_default_scale", 1)

    response = client.post(
        "/api/roof/satellite-tile",
        json={"location": {"latitude": 30.0, "longitude": 31.0}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["zoom"] == 19
    assert body["size_px"] == 320
    assert body["scale"] == 1


def test_satellite_tile_rejects_oversize_image():
    response = client.post(
        "/api/roof/satellite-tile",
        json={"location": {"latitude": 30.0, "longitude": 31.0}, "size_px": 5000},
    )
    assert response.status_code == 422
