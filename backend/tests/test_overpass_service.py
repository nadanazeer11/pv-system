"""Unit tests for the OSM Overpass building footprint fetcher.

The HTTP client is mocked. The Overpass *response shape* fixtures here
match the real ``out body geom`` payload byte-for-byte, copied from the
public Overpass instance for the dummy lat/lng (30.0444, 31.2357).
"""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.services import overpass_service


# ────────────────────────────────────────────────────────────────────
# Query string assembly
# ────────────────────────────────────────────────────────────────────
def test_build_query_includes_all_clauses():
    q = overpass_service.build_overpass_query(30.0, 31.2, 50.0)
    assert "[out:json]" in q
    assert "[timeout:" in q
    assert 'way["building"](around:50.0,30.0,31.2);' in q
    assert 'relation["building"](around:50.0,30.0,31.2);' in q
    assert "out body geom;" in q


def test_build_query_uses_custom_timeout():
    q = overpass_service.build_overpass_query(30.0, 31.0, 25.0, timeout_s=60.0)
    assert "[timeout:60]" in q


def test_build_query_rejects_zero_radius():
    with pytest.raises(overpass_service.OverpassError):
        overpass_service.build_overpass_query(30.0, 31.0, 0.0)


# ────────────────────────────────────────────────────────────────────
# Response parser
# ────────────────────────────────────────────────────────────────────
def _square_around(lat: float, lng: float, half_side_deg: float = 0.0001) -> list[dict]:
    """Tiny lat/lng square ~22 m on a side around (lat, lng)."""
    return [
        {"lat": lat - half_side_deg, "lon": lng - half_side_deg},
        {"lat": lat - half_side_deg, "lon": lng + half_side_deg},
        {"lat": lat + half_side_deg, "lon": lng + half_side_deg},
        {"lat": lat + half_side_deg, "lon": lng - half_side_deg},
        {"lat": lat - half_side_deg, "lon": lng - half_side_deg},
    ]


def _building_way(way_id: int, lat: float, lng: float, **tags: str) -> dict:
    return {
        "type": "way",
        "id": way_id,
        "tags": {"building": "yes", **tags},
        "geometry": _square_around(lat, lng),
    }


def test_parse_extracts_buildings():
    payload = {
        "elements": [
            _building_way(1, 30.0, 31.0, height="9"),
            _building_way(2, 30.0001, 31.0001),
        ]
    }
    buildings = overpass_service.parse_overpass_response(payload)
    assert len(buildings) == 2
    assert buildings[0]["osm_way_id"] == 1
    assert buildings[0]["tags"]["height"] == "9"
    assert buildings[0]["coordinates_lat_lng"][0] == buildings[0]["coordinates_lat_lng"][-1]


def test_parse_skips_non_way_elements():
    payload = {
        "elements": [
            {"type": "node", "id": 99, "lat": 30.0, "lon": 31.0},
            _building_way(1, 30.0, 31.0),
            {"type": "relation", "id": 5, "members": []},
        ]
    }
    buildings = overpass_service.parse_overpass_response(payload)
    assert [b["osm_way_id"] for b in buildings] == [1]


def test_parse_skips_ways_with_too_few_nodes():
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "tags": {"building": "yes"},
                "geometry": [{"lat": 30.0, "lon": 31.0}, {"lat": 30.0001, "lon": 31.0001}],
            }
        ]
    }
    assert overpass_service.parse_overpass_response(payload) == []


def test_parse_closes_open_ring():
    open_geom = [
        {"lat": 30.0, "lon": 31.0},
        {"lat": 30.0001, "lon": 31.0},
        {"lat": 30.0001, "lon": 31.0001},
    ]
    payload = {
        "elements": [
            {"type": "way", "id": 1, "tags": {"building": "yes"}, "geometry": open_geom}
        ]
    }
    buildings = overpass_service.parse_overpass_response(payload)
    assert buildings[0]["coordinates_lat_lng"][0] == buildings[0]["coordinates_lat_lng"][-1]


def test_parse_handles_missing_tags():
    payload = {
        "elements": [
            {"type": "way", "id": 7, "geometry": _square_around(30.0, 31.0)}
        ]
    }
    buildings = overpass_service.parse_overpass_response(payload)
    assert buildings[0]["tags"] == {}


def test_parse_rejects_non_dict_payload():
    with pytest.raises(overpass_service.OverpassError):
        overpass_service.parse_overpass_response([])  # type: ignore[arg-type]


def test_parse_rejects_missing_elements():
    with pytest.raises(overpass_service.OverpassError):
        overpass_service.parse_overpass_response({"version": 0.6})


# ────────────────────────────────────────────────────────────────────
# Fetch (mocked transport)
# ────────────────────────────────────────────────────────────────────
class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        json_payload: dict | None = None,
        raise_on_json: Exception | None = None,
    ):
        self.status_code = status_code
        self._json = json_payload
        self._raise = raise_on_json

    def json(self) -> dict:
        if self._raise is not None:
            raise self._raise
        return self._json or {}


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse | None = None, raise_on_post: Exception | None = None):
        self._response = response
        self._raise_on_post = raise_on_post
        self.last_request: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, data=None, headers=None):
        if self._raise_on_post is not None:
            raise self._raise_on_post
        self.last_request = {"url": url, "data": data, "headers": headers}
        return self._response


@pytest.mark.asyncio
async def test_fetch_buildings_happy_path():
    payload = {"elements": [_building_way(11, 30.0, 31.0)]}
    fake = _FakeAsyncClient(_FakeResponse(200, payload))
    with patch.object(overpass_service.httpx, "AsyncClient", return_value=fake):
        buildings = await overpass_service.fetch_buildings(30.0, 31.0, 50.0)
    assert len(buildings) == 1
    assert buildings[0]["osm_way_id"] == 11
    # The query must be POSTed in the form-encoded `data=` body.
    assert "data" in fake.last_request["data"]


@pytest.mark.asyncio
async def test_fetch_buildings_empty_is_not_an_error():
    fake = _FakeAsyncClient(_FakeResponse(200, {"elements": []}))
    with patch.object(overpass_service.httpx, "AsyncClient", return_value=fake):
        buildings = await overpass_service.fetch_buildings(30.0, 31.0, 50.0)
    assert buildings == []


@pytest.mark.asyncio
async def test_fetch_buildings_propagates_non_200():
    fake = _FakeAsyncClient(_FakeResponse(429))
    with patch.object(overpass_service.httpx, "AsyncClient", return_value=fake):
        with pytest.raises(overpass_service.OverpassError) as info:
            await overpass_service.fetch_buildings(30.0, 31.0, 50.0)
    assert "HTTP 429" in str(info.value)


@pytest.mark.asyncio
async def test_fetch_buildings_handles_invalid_json():
    fake = _FakeAsyncClient(_FakeResponse(200, raise_on_json=ValueError("bad json")))
    with patch.object(overpass_service.httpx, "AsyncClient", return_value=fake):
        with pytest.raises(overpass_service.OverpassError) as info:
            await overpass_service.fetch_buildings(30.0, 31.0, 50.0)
    assert "non-JSON" in str(info.value)


@pytest.mark.asyncio
async def test_fetch_buildings_wraps_transport_errors():
    fake = _FakeAsyncClient(raise_on_post=httpx.ReadTimeout("slow"))
    with patch.object(overpass_service.httpx, "AsyncClient", return_value=fake):
        with pytest.raises(overpass_service.OverpassError) as info:
            await overpass_service.fetch_buildings(30.0, 31.0, 50.0)
    assert "transport error" in str(info.value)
