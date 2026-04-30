"""Integration tests for the Day-11 ``/api/roof/analyze`` endpoint.

The Day-10 detection layer is exercised by ``test_roof_detection`` and
``test_roof_router``; this module focuses on the new orchestration:

* CV refinement runs end-to-end when a satellite tile is fetched.
* CV failures (transport, missing key, bad image) degrade gracefully.
* OSM-only requests (``enable_cv=False``) skip the network fetch.
* Tilt and azimuth are populated from polygon + tags.
"""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas.inputs import Location
from app.services import gmaps_static, overpass_service, roof_detection

client = TestClient(app)

_PIN = Location(latitude=30.0444, longitude=31.2357)


def _square(lat: float, lng: float, h: float = 0.0001) -> list[tuple[float, float]]:
    return [
        (lat - h, lng - h),
        (lat - h, lng + h),
        (lat + h, lng + h),
        (lat + h, lng - h),
        (lat - h, lng - h),
    ]


def _png_with_central_dark_square(size_px: int = 200) -> bytes:
    arr = np.full((size_px, size_px), 0.9, dtype=np.float32)
    margin = size_px // 4
    arr[margin:-margin, margin:-margin] = 0.1
    arr_u8 = (arr * 255.0).astype(np.uint8)
    img = Image.fromarray(arr_u8, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _building(way_id: int, ring: list[tuple[float, float]], **tags: str) -> dict:
    return {
        "osm_way_id": way_id,
        "coordinates_lat_lng": ring,
        "tags": tags or {"building": "yes"},
    }


# ────────────────────────────────────────────────────────────────────
# Service-level orchestration
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_analyze_roof_populates_cv_fields_when_image_loads(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    ring = _square(_PIN.latitude, _PIN.longitude)
    raw = [_building(1, ring, **{"roof:shape": "flat"})]
    img = _png_with_central_dark_square(64)

    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ), patch.object(gmaps_static, "fetch_static_map", new=AsyncMock(return_value=img)):
        result = await roof_detection.analyze_roof(_PIN)

    assert result.primary_roof is not None
    assert result.segmentation_polygon_lat_lng is not None
    assert len(result.segmentation_polygon_lat_lng) == 5
    assert result.segmentation_area_m2 == pytest.approx(429.0, rel=0.05)
    assert result.segmentation_confidence is not None
    assert 0.0 <= result.segmentation_confidence <= 1.0
    assert result.estimated_tilt_deg == pytest.approx(_PIN.latitude)
    assert result.estimated_tilt_source == "flat-roof-default-cairo-optimum"
    assert result.estimated_azimuth_deg == pytest.approx(180.0)
    assert result.estimated_azimuth_source == "fallback-south"


@pytest.mark.asyncio
async def test_analyze_roof_pitched_polygon_fills_azimuth_from_geometry(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "")
    h_lat, h_lng = 0.00002, 0.00010
    ring = [
        (_PIN.latitude - h_lat, _PIN.longitude - h_lng),
        (_PIN.latitude - h_lat, _PIN.longitude + h_lng),
        (_PIN.latitude + h_lat, _PIN.longitude + h_lng),
        (_PIN.latitude + h_lat, _PIN.longitude - h_lng),
        (_PIN.latitude - h_lat, _PIN.longitude - h_lng),
    ]
    raw = [_building(1, ring, **{"roof:shape": "gabled", "roof:angle": "27"})]

    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ):
        result = await roof_detection.analyze_roof(_PIN)

    assert result.estimated_tilt_deg == pytest.approx(27.0)
    assert result.estimated_tilt_source == "osm:roof:angle"
    # Long edge runs east-west → panel face is south.
    assert result.estimated_azimuth_deg == pytest.approx(180.0, abs=10.0)
    assert "polygon-long-edge" in result.estimated_azimuth_source


@pytest.mark.asyncio
async def test_analyze_roof_disabling_cv_skips_image_fetch(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    ring = _square(_PIN.latitude, _PIN.longitude)
    raw = [_building(1, ring)]
    fetch_mock = AsyncMock()

    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ), patch.object(gmaps_static, "fetch_static_map", new=fetch_mock):
        result = await roof_detection.analyze_roof(_PIN, enable_cv=False)

    fetch_mock.assert_not_called()
    assert result.segmentation_polygon_lat_lng is not None
    assert result.segmentation_confidence == 0.0
    assert any("CV refinement disabled" in n for n in result.notes)


@pytest.mark.asyncio
async def test_analyze_roof_handles_image_fetch_failure(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    ring = _square(_PIN.latitude, _PIN.longitude)
    raw = [_building(1, ring)]
    failing_fetch = AsyncMock(
        side_effect=gmaps_static.GoogleMapsError("HTTP 503 from upstream")
    )

    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ), patch.object(gmaps_static, "fetch_static_map", new=failing_fetch):
        result = await roof_detection.analyze_roof(_PIN)

    assert result.primary_roof is not None
    assert result.segmentation_polygon_lat_lng is not None
    # No image → 0 confidence, but the regularised polygon is still returned.
    assert result.segmentation_confidence == 0.0
    assert any("satellite tile fetch failed" in n for n in result.notes)


@pytest.mark.asyncio
async def test_analyze_roof_handles_corrupt_image_bytes(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    ring = _square(_PIN.latitude, _PIN.longitude)
    raw = [_building(1, ring)]
    corrupt = AsyncMock(return_value=b"not really a PNG")

    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ), patch.object(gmaps_static, "fetch_static_map", new=corrupt):
        result = await roof_detection.analyze_roof(_PIN)

    assert result.primary_roof is not None
    # The corrupt image should be reported via a CV-failed note.
    assert any("CV refinement failed" in n for n in result.notes)
    assert result.segmentation_confidence is None


@pytest.mark.asyncio
async def test_analyze_roof_no_buildings_skips_cv(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    fetch_mock = AsyncMock()
    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=[])
    ), patch.object(gmaps_static, "fetch_static_map", new=fetch_mock):
        result = await roof_detection.analyze_roof(_PIN)
    fetch_mock.assert_not_called()
    assert result.primary_roof is None
    assert result.segmentation_polygon_lat_lng is None
    assert any("no primary roof polygon" in n for n in result.notes)


# ────────────────────────────────────────────────────────────────────
# Router shape
# ────────────────────────────────────────────────────────────────────
def test_analyze_endpoint_returns_200_with_cv_fields(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    ring = _square(_PIN.latitude, _PIN.longitude)
    raw = [_building(1, ring, **{"roof:shape": "flat"})]
    img = _png_with_central_dark_square(64)

    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ), patch.object(gmaps_static, "fetch_static_map", new=AsyncMock(return_value=img)):
        response = client.post(
            "/api/roof/analyze",
            json={"location": {"latitude": _PIN.latitude, "longitude": _PIN.longitude}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["primary_roof"] is not None
    assert body["segmentation_polygon_lat_lng"] is not None
    assert body["estimated_tilt_deg"] == pytest.approx(_PIN.latitude)
    assert body["estimated_azimuth_deg"] == pytest.approx(180.0)
    assert body["estimated_tilt_source"] == "flat-roof-default-cairo-optimum"
    assert body["estimated_azimuth_source"] == "fallback-south"


def test_analyze_endpoint_overpass_failure_becomes_502(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    with patch.object(
        overpass_service,
        "fetch_buildings",
        new=AsyncMock(side_effect=overpass_service.OverpassError("upstream down")),
    ):
        response = client.post(
            "/api/roof/analyze",
            json={"location": {"latitude": _PIN.latitude, "longitude": _PIN.longitude}},
        )
    assert response.status_code == 502
    assert "OSM Overpass fetch failed" in response.json()["detail"]


def test_analyze_endpoint_rejects_invalid_radius():
    response = client.post(
        "/api/roof/analyze",
        json={
            "location": {"latitude": _PIN.latitude, "longitude": _PIN.longitude},
            "search_radius_m": -10.0,
        },
    )
    assert response.status_code == 422


def test_analyze_endpoint_disable_cv_returns_polygon_without_image_fetch(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    ring = _square(_PIN.latitude, _PIN.longitude)
    raw = [_building(1, ring)]
    fetch_mock = AsyncMock()
    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ), patch.object(gmaps_static, "fetch_static_map", new=fetch_mock):
        response = client.post(
            "/api/roof/analyze",
            json={
                "location": {"latitude": _PIN.latitude, "longitude": _PIN.longitude},
                "enable_cv": False,
            },
        )
    fetch_mock.assert_not_called()
    assert response.status_code == 200
    body = response.json()
    assert body["segmentation_polygon_lat_lng"] is not None
    assert body["segmentation_confidence"] == 0.0


def test_analyze_endpoint_no_buildings_returns_200_with_null_cv(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=[])
    ):
        response = client.post(
            "/api/roof/analyze",
            json={"location": {"latitude": _PIN.latitude, "longitude": _PIN.longitude}},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["primary_roof"] is None
    assert body["segmentation_polygon_lat_lng"] is None
    assert body["estimated_tilt_deg"] is None
    assert body["estimated_azimuth_deg"] is None


def test_analyze_endpoint_image_failure_degrades_to_osm_only(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    ring = _square(_PIN.latitude, _PIN.longitude)
    raw = [_building(1, ring)]
    failing = AsyncMock(side_effect=gmaps_static.GoogleMapsError("transport failure"))

    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=raw)
    ), patch.object(gmaps_static, "fetch_static_map", new=failing):
        response = client.post(
            "/api/roof/analyze",
            json={"location": {"latitude": _PIN.latitude, "longitude": _PIN.longitude}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["primary_roof"] is not None
    assert body["segmentation_polygon_lat_lng"] is not None
    assert body["segmentation_confidence"] == 0.0
    assert any("satellite tile fetch failed" in n for n in body["notes"])
