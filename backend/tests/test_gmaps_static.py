"""Unit tests for the Google Maps Static service.

The HTTP layer is mocked with ``unittest.mock.patch`` so the test suite
never reaches Google. The mathematical helpers are tested against
closed-form Web Mercator values published in the official Google Maps
developer documentation.
"""
from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.services import gmaps_static


# ────────────────────────────────────────────────────────────────────
# Ground-resolution math
# ────────────────────────────────────────────────────────────────────
def test_meters_per_pixel_at_equator_zoom_zero():
    # Documented Google constant: 156 543.034 m/px at the equator,
    # zoom 0, scale 1.
    assert gmaps_static.meters_per_pixel(0.0, 0, 1) == pytest.approx(156543.034, rel=1e-5)


def test_meters_per_pixel_halves_each_zoom_level():
    base = gmaps_static.meters_per_pixel(0.0, 1, 1)
    next_zoom = gmaps_static.meters_per_pixel(0.0, 2, 1)
    assert base == pytest.approx(2.0 * next_zoom, rel=1e-9)


def test_meters_per_pixel_halves_with_scale_two():
    base = gmaps_static.meters_per_pixel(0.0, 10, 1)
    hidpi = gmaps_static.meters_per_pixel(0.0, 10, 2)
    assert hidpi == pytest.approx(base / 2.0, rel=1e-9)


def test_meters_per_pixel_uses_cosine_latitude():
    # At Cairo (~30°N), zoom 20, scale 2: documented ~14 cm/px.
    cairo = gmaps_static.meters_per_pixel(30.0444, 20, 2)
    assert cairo == pytest.approx(
        156543.03392 * math.cos(math.radians(30.0444)) / (2**20) / 2, rel=1e-9
    )
    # Documented Cairo (φ≈30°) zoom 20 scale 2 ≈ 6.5 cm/pixel.
    assert 0.05 < cairo < 0.10


def test_meters_per_pixel_rejects_negative_zoom():
    with pytest.raises(gmaps_static.GoogleMapsError):
        gmaps_static.meters_per_pixel(30.0, -1, 1)


def test_meters_per_pixel_rejects_zero_scale():
    with pytest.raises(gmaps_static.GoogleMapsError):
        gmaps_static.meters_per_pixel(30.0, 18, 0)


# ────────────────────────────────────────────────────────────────────
# URL builder
# ────────────────────────────────────────────────────────────────────
def test_build_url_requires_api_key(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "")
    with pytest.raises(gmaps_static.GoogleMapsError) as info:
        gmaps_static.build_static_map_url(30.0, 31.2)
    assert "GOOGLE_MAPS_API_KEY" in str(info.value)


def test_build_url_includes_all_expected_parameters(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "TEST-KEY-123")
    url = gmaps_static.build_static_map_url(30.0444, 31.2357, zoom=19, size_px=512, scale=2)

    parsed = urlparse(url)
    assert parsed.netloc == "maps.googleapis.com"
    assert parsed.path == "/maps/api/staticmap"

    qs = parse_qs(parsed.query)
    assert qs["center"] == ["30.044400,31.235700"]
    assert qs["zoom"] == ["19"]
    assert qs["size"] == ["512x512"]
    assert qs["scale"] == ["2"]
    assert qs["maptype"] == ["satellite"]
    assert qs["format"] == ["png"]
    assert qs["key"] == ["TEST-KEY-123"]


def test_build_url_uses_configured_defaults_when_unspecified(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    monkeypatch.setattr(gmaps_static.settings, "gmaps_static_default_zoom", 18)
    monkeypatch.setattr(gmaps_static.settings, "gmaps_static_default_size_px", 320)
    monkeypatch.setattr(gmaps_static.settings, "gmaps_static_default_scale", 1)

    url = gmaps_static.build_static_map_url(30.0, 31.0)
    qs = parse_qs(urlparse(url).query)
    assert qs["zoom"] == ["18"]
    assert qs["size"] == ["320x320"]
    assert qs["scale"] == ["1"]


def test_describe_tile_consistency(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    desc = gmaps_static.describe_tile(30.0, zoom=20, size_px=640, scale=2)
    assert desc["zoom"] == 20
    assert desc["size_px"] == 640
    assert desc["scale"] == 2
    assert desc["tile_width_m"] == pytest.approx(
        desc["meters_per_pixel"] * 640 * 2, rel=1e-9
    )
    assert desc["tile_width_m"] == desc["tile_height_m"]


# ────────────────────────────────────────────────────────────────────
# Fetch (mocked transport)
# ────────────────────────────────────────────────────────────────────
class _FakeResponse:
    def __init__(self, status_code: int, content: bytes, content_type: str = "image/png"):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse | None = None, raise_on_get: Exception | None = None):
        self._response = response
        self._raise_on_get = raise_on_get

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        if self._raise_on_get is not None:
            raise self._raise_on_get
        return self._response


@pytest.mark.asyncio
async def test_fetch_static_map_returns_bytes(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")

    fake = _FakeAsyncClient(_FakeResponse(200, b"\x89PNG\r\n\x1a\nFAKE", "image/png"))
    with patch.object(gmaps_static.httpx, "AsyncClient", return_value=fake):
        data = await gmaps_static.fetch_static_map(30.0, 31.0)
    assert data.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_fetch_static_map_propagates_non_200(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    fake = _FakeAsyncClient(_FakeResponse(403, b"forbidden", "text/plain"))
    with patch.object(gmaps_static.httpx, "AsyncClient", return_value=fake):
        with pytest.raises(gmaps_static.GoogleMapsError) as info:
            await gmaps_static.fetch_static_map(30.0, 31.0)
    assert "HTTP 403" in str(info.value)


@pytest.mark.asyncio
async def test_fetch_static_map_rejects_non_image_content_type(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    fake = _FakeAsyncClient(_FakeResponse(200, b"oops", "application/json"))
    with patch.object(gmaps_static.httpx, "AsyncClient", return_value=fake):
        with pytest.raises(gmaps_static.GoogleMapsError) as info:
            await gmaps_static.fetch_static_map(30.0, 31.0)
    assert "non-image" in str(info.value)


@pytest.mark.asyncio
async def test_fetch_static_map_wraps_transport_errors(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "K")
    fake = _FakeAsyncClient(raise_on_get=httpx.ConnectError("boom"))
    with patch.object(gmaps_static.httpx, "AsyncClient", return_value=fake):
        with pytest.raises(gmaps_static.GoogleMapsError) as info:
            await gmaps_static.fetch_static_map(30.0, 31.0)
    assert "transport error" in str(info.value)


@pytest.mark.asyncio
async def test_fetch_static_map_requires_api_key(monkeypatch):
    monkeypatch.setattr(gmaps_static.settings, "google_maps_api_key", "")
    with pytest.raises(gmaps_static.GoogleMapsError):
        await gmaps_static.fetch_static_map(30.0, 31.0)
