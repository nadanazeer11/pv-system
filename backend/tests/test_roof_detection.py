"""Tests for the OSM-based roof detection orchestrator.

These tests do not touch the network. They drive
:func:`roof_detection.detect_roof` by patching ``overpass_service.fetch_buildings``
to return synthetic building dictionaries — the same shape the real
Overpass parser produces — and patching the Google Maps URL builder
where required.
"""
from __future__ import annotations

import math
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.inputs import Location
from app.services import gmaps_static, overpass_service, roof_detection


# ────────────────────────────────────────────────────────────────────
# Geometry helpers
# ────────────────────────────────────────────────────────────────────
_PIN = Location(latitude=30.0444, longitude=31.2357)  # Tahrir Sq, Cairo


def _square_around(lat: float, lng: float, half_side_deg: float = 0.0001) -> list[tuple[float, float]]:
    """Closed lat/lng ring forming a tiny square ~22 m on a side at φ≈30°."""
    return [
        (lat - half_side_deg, lng - half_side_deg),
        (lat - half_side_deg, lng + half_side_deg),
        (lat + half_side_deg, lng + half_side_deg),
        (lat + half_side_deg, lng - half_side_deg),
        (lat - half_side_deg, lng - half_side_deg),
    ]


def _building(way_id: int, ring: list[tuple[float, float]], **tags: str) -> dict:
    return {
        "osm_way_id": way_id,
        "coordinates_lat_lng": ring,
        "tags": tags or {"building": "yes"},
    }


def test_project_origin_maps_to_zero():
    out = roof_detection.project_lat_lng_to_meters(30.0, 31.0, [(30.0, 31.0)])
    assert out == [(0.0, 0.0)]


def test_project_one_degree_latitude_is_about_111_km():
    [(_, y)] = roof_detection.project_lat_lng_to_meters(30.0, 31.0, [(31.0, 31.0)])
    # Equirectangular: y = R * Δφ (rad) = 6378137 * π/180 ≈ 111319.49 m
    assert y == pytest.approx(111319.49, rel=1e-4)


def test_project_one_degree_longitude_at_30N_is_about_96_km():
    [(x, _)] = roof_detection.project_lat_lng_to_meters(30.0, 31.0, [(30.0, 32.0)])
    expected = 6378137.0 * math.cos(math.radians(30.0)) * math.radians(1.0)
    assert x == pytest.approx(expected, rel=1e-9)
    assert 96_000 < x < 97_000


def test_assemble_candidates_computes_area_in_square_metres():
    # Square with half-side 0.0001° at 30°N: side ≈ 0.0002° × 111 320 m
    # in latitude, and 0.0002° × cos(30°) × 111 320 m in longitude.
    # Area ≈ 22.264 m × 19.281 m ≈ 429 m².
    ring = _square_around(_PIN.latitude, _PIN.longitude)
    candidates = roof_detection.assemble_candidates(
        [_building(1, ring)], _PIN.latitude, _PIN.longitude
    )
    assert len(candidates) == 1
    assert 400.0 < candidates[0].area_m2 < 460.0
    assert candidates[0].contains_query_point is True


def test_assemble_candidates_orders_containing_first_then_by_area():
    inner_ring = _square_around(_PIN.latitude, _PIN.longitude, half_side_deg=0.00005)
    outer_ring = _square_around(_PIN.latitude, _PIN.longitude, half_side_deg=0.00012)
    far_ring = _square_around(_PIN.latitude + 0.001, _PIN.longitude + 0.001, half_side_deg=0.0001)

    candidates = roof_detection.assemble_candidates(
        [_building(1, far_ring), _building(2, outer_ring), _building(3, inner_ring)],
        _PIN.latitude,
        _PIN.longitude,
    )
    # Inner (smallest containing) first, then outer (also containing),
    # then far (non-containing, ordered by distance).
    assert [c.osm_way_id for c in candidates] == [3, 2, 1]
    assert candidates[0].contains_query_point is True
    assert candidates[1].contains_query_point is True
    assert candidates[2].contains_query_point is False


def test_assemble_candidates_skips_malformed_polygon():
    bad = _building(99, [(30.0, 31.0), (30.0, 31.0)])
    good = _building(1, _square_around(_PIN.latitude, _PIN.longitude))
    candidates = roof_detection.assemble_candidates(
        [bad, good], _PIN.latitude, _PIN.longitude
    )
    assert [c.osm_way_id for c in candidates] == [1]


# ────────────────────────────────────────────────────────────────────
# Selection logic
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_detect_roof_selects_innermost_containing_polygon(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    inner = _building(2, _square_around(_PIN.latitude, _PIN.longitude, 0.00005))
    outer = _building(1, _square_around(_PIN.latitude, _PIN.longitude, 0.00015))
    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=[outer, inner])
    ):
        result = await roof_detection.detect_roof(_PIN)
    assert result.primary_roof is not None
    assert result.primary_roof.osm_way_id == 2
    assert result.primary_roof.contains_query_point is True
    assert result.detection_source == "osm-overpass"


@pytest.mark.asyncio
async def test_detect_roof_falls_back_to_nearest_when_no_containment(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    near = _building(
        1, _square_around(_PIN.latitude + 0.0002, _PIN.longitude + 0.0002, 0.00008)
    )
    far = _building(
        2, _square_around(_PIN.latitude + 0.0010, _PIN.longitude + 0.0010, 0.00008)
    )
    with patch.object(
        overpass_service, "fetch_buildings", new=AsyncMock(return_value=[far, near])
    ):
        result = await roof_detection.detect_roof(_PIN)
    assert result.primary_roof is not None
    assert result.primary_roof.osm_way_id == 1
    assert result.primary_roof.contains_query_point is False
    assert any("falling back" in note for note in result.notes)


@pytest.mark.asyncio
async def test_detect_roof_handles_no_buildings(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    with patch.object(overpass_service, "fetch_buildings", new=AsyncMock(return_value=[])):
        result = await roof_detection.detect_roof(_PIN)
    assert result.primary_roof is None
    assert result.candidates == []
    assert any("No OSM building footprints" in note for note in result.notes)


@pytest.mark.asyncio
async def test_detect_roof_caps_radius_at_server_max(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    monkeypatch.setattr(roof_detection.settings, "roof_search_radius_max_m", 100.0)
    captured: dict = {}

    async def fake_fetch(lat, lng, radius):
        captured["radius"] = radius
        return []

    with patch.object(overpass_service, "fetch_buildings", new=fake_fetch):
        result = await roof_detection.detect_roof(_PIN, search_radius_m=10000.0)
    assert captured["radius"] == 100.0
    assert result.search_radius_m == 100.0


@pytest.mark.asyncio
async def test_detect_roof_uses_default_radius_when_none(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    monkeypatch.setattr(roof_detection.settings, "roof_search_radius_m", 75.0)
    captured: dict = {}

    async def fake_fetch(lat, lng, radius):
        captured["radius"] = radius
        return []

    with patch.object(overpass_service, "fetch_buildings", new=fake_fetch):
        result = await roof_detection.detect_roof(_PIN)
    assert captured["radius"] == 75.0
    assert result.search_radius_m == 75.0


@pytest.mark.asyncio
async def test_detect_roof_propagates_overpass_failure_as_orchestrator_error(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    with patch.object(
        overpass_service,
        "fetch_buildings",
        new=AsyncMock(side_effect=overpass_service.OverpassError("upstream down")),
    ):
        with pytest.raises(roof_detection.RoofDetectionError) as info:
            await roof_detection.detect_roof(_PIN)
    assert "OSM Overpass fetch failed" in str(info.value)


# ────────────────────────────────────────────────────────────────────
# GMaps integration (still no network — patched URL builder)
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_detect_roof_includes_satellite_url_when_key_present(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "TEST-KEY")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "TEST-KEY")
    ring = _square_around(_PIN.latitude, _PIN.longitude)
    with patch.object(
        overpass_service,
        "fetch_buildings",
        new=AsyncMock(return_value=[_building(1, ring)]),
    ):
        result = await roof_detection.detect_roof(_PIN)
    assert result.satellite_tile_url is not None
    assert "maps.googleapis.com" in result.satellite_tile_url
    assert "key=TEST-KEY" in result.satellite_tile_url
    assert result.meters_per_pixel is not None and result.meters_per_pixel > 0
    # No "satellite tile unavailable" notes when the key is present.
    assert not any("Satellite tile unavailable" in n for n in result.notes)


@pytest.mark.asyncio
async def test_detect_roof_emits_note_when_gmaps_key_missing(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "")
    ring = _square_around(_PIN.latitude, _PIN.longitude)
    with patch.object(
        overpass_service,
        "fetch_buildings",
        new=AsyncMock(return_value=[_building(1, ring)]),
    ):
        result = await roof_detection.detect_roof(_PIN)
    assert result.satellite_tile_url is None
    assert result.meters_per_pixel is None
    assert any("Satellite tile unavailable" in n for n in result.notes)
    # OSM detection still succeeded — primary roof is filled in.
    assert result.primary_roof is not None


@pytest.mark.asyncio
async def test_detect_roof_centres_tile_on_pin_when_no_buildings(monkeypatch):
    monkeypatch.setattr(roof_detection.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    with patch.object(overpass_service, "fetch_buildings", new=AsyncMock(return_value=[])):
        result = await roof_detection.detect_roof(_PIN)
    assert result.satellite_tile_url is not None
    # URL encodes the comma between lat and lng as %2C.
    assert f"{_PIN.latitude:.6f}%2C{_PIN.longitude:.6f}" in result.satellite_tile_url


# ────────────────────────────────────────────────────────────────────
# Validation
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_detect_roof_rejects_non_positive_radius():
    with pytest.raises(roof_detection.RoofDetectionError):
        await roof_detection.detect_roof(_PIN, search_radius_m=-5.0)
