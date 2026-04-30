"""Unit tests for the Day-11 CV refinement service.

The tests are entirely synthetic — every PNG is generated in-process
with Pillow so the suite stays offline-safe and fast.
"""
from __future__ import annotations

import io
import math

import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.services import roof_segmentation
from app.services.roof_segmentation import (
    RefinementResult,
    RoofSegmentationError,
    edge_alignment_confidence,
    lat_lng_to_pixel,
    load_grayscale,
    refine_polygon,
    regularize_polygon,
    sobel_magnitude,
)


# Tahrir Square, Cairo (the canonical anchor used elsewhere in the suite).
_PIN_LAT = 30.0444
_PIN_LNG = 31.2357


def _square_around(lat: float, lng: float, half_side_deg: float = 0.0001) -> list[tuple[float, float]]:
    return [
        (lat - half_side_deg, lng - half_side_deg),
        (lat - half_side_deg, lng + half_side_deg),
        (lat + half_side_deg, lng + half_side_deg),
        (lat + half_side_deg, lng - half_side_deg),
        (lat - half_side_deg, lng - half_side_deg),
    ]


def _png_bytes_from_array(arr: np.ndarray) -> bytes:
    """Encode an HxW float array in [0,1] as a PNG (grayscale)."""
    arr_u8 = np.clip(arr * 255.0, 0.0, 255.0).astype(np.uint8)
    img = Image.fromarray(arr_u8, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ────────────────────────────────────────────────────────────────────
# Image utilities
# ────────────────────────────────────────────────────────────────────
def test_load_grayscale_returns_normalised_float_array():
    arr = np.full((16, 16), 0.5, dtype=np.float32)
    decoded = load_grayscale(_png_bytes_from_array(arr))
    assert decoded.shape == (16, 16)
    assert decoded.dtype == np.float32
    # Round-trip through 8-bit PNG, so allow ±1/255 quantisation noise.
    assert np.allclose(decoded, 0.5, atol=1.5 / 255.0)


def test_load_grayscale_rejects_corrupt_bytes():
    with pytest.raises(RoofSegmentationError):
        load_grayscale(b"not a real PNG file")


def test_load_grayscale_handles_rgb_images():
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)
    rgb[..., 0] = 200
    img = Image.fromarray(rgb, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    decoded = load_grayscale(buf.getvalue())
    assert decoded.shape == (8, 8)
    # PIL grayscale conversion uses ITU-R BT.601 luma weights (R=0.299).
    assert np.allclose(decoded, 0.299 * 200 / 255.0, atol=2.0 / 255.0)


def test_sobel_magnitude_is_nonnegative_everywhere():
    arr = np.linspace(0.0, 1.0, 32 * 32).reshape(32, 32).astype(np.float32)
    mag = sobel_magnitude(arr)
    assert mag.shape == arr.shape
    assert (mag >= 0).all()


def test_sobel_magnitude_rejects_too_small_image():
    with pytest.raises(RoofSegmentationError):
        sobel_magnitude(np.zeros((2, 2), dtype=np.float32))


def test_sobel_magnitude_picks_up_a_step_edge():
    """A vertical step from 0 to 1 should produce a clear gradient ridge."""
    arr = np.zeros((20, 20), dtype=np.float32)
    arr[:, 10:] = 1.0
    mag = sobel_magnitude(arr)
    # Gradient magnitudes near col=10 must be strongly above magnitudes
    # in the uniform regions on either side.
    edge_band = mag[5:15, 9:11]
    flat_band = mag[5:15, 0:5]
    assert edge_band.mean() > 0.1
    assert edge_band.mean() > 5.0 * flat_band.mean() + 1e-6


# ────────────────────────────────────────────────────────────────────
# Lat/lng → pixel projection
# ────────────────────────────────────────────────────────────────────
def test_lat_lng_to_pixel_centre_maps_to_image_centre():
    col, row = lat_lng_to_pixel(
        _PIN_LAT,
        _PIN_LNG,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=640,
        scale=2,
        zoom=20,
    )
    assert col == pytest.approx(640.0, abs=1e-6)
    assert row == pytest.approx(640.0, abs=1e-6)


def test_lat_lng_to_pixel_north_displacement_decreases_row():
    centre_col, centre_row = lat_lng_to_pixel(
        _PIN_LAT,
        _PIN_LNG,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=64,
        scale=1,
        zoom=20,
    )
    # 1 m north of the pin: row decreases (north is up in image space).
    one_metre_lat = _PIN_LAT + 1.0 / (math.radians(1.0) * 6_378_137.0)
    _, north_row = lat_lng_to_pixel(
        one_metre_lat,
        _PIN_LNG,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=64,
        scale=1,
        zoom=20,
    )
    assert north_row < centre_row


def test_lat_lng_to_pixel_east_displacement_increases_col():
    centre_col, _ = lat_lng_to_pixel(
        _PIN_LAT,
        _PIN_LNG,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=64,
        scale=1,
        zoom=20,
    )
    one_metre_lng = _PIN_LNG + 1.0 / (
        math.cos(math.radians(_PIN_LAT)) * math.radians(1.0) * 6_378_137.0
    )
    east_col, _ = lat_lng_to_pixel(
        _PIN_LAT,
        one_metre_lng,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=64,
        scale=1,
        zoom=20,
    )
    assert east_col > centre_col


# ────────────────────────────────────────────────────────────────────
# Regularisation
# ────────────────────────────────────────────────────────────────────
def test_regularize_polygon_returns_closed_4_corner_rectangle():
    ring = _square_around(_PIN_LAT, _PIN_LNG)
    rect, area_m2 = regularize_polygon(ring, origin_lat=_PIN_LAT, origin_lng=_PIN_LNG)
    assert len(rect) == 5  # 4 corners + closure repeat
    assert rect[0] == rect[-1]
    assert area_m2 == pytest.approx(429.0, rel=0.05)  # ~22.26 m × 19.28 m


def test_regularize_polygon_collapses_jagged_polygon():
    """A noisy polygon around a clean rectangle should regularise back to it."""
    base = _square_around(_PIN_LAT, _PIN_LNG, 0.0001)
    # Insert an extra "dent" mid-edge that the rectangle should ignore.
    noisy = list(base[:2]) + [
        (base[1][0], base[1][1] + 0.000005)  # 0.5 m east bump
    ] + list(base[2:])
    rect, area_m2 = regularize_polygon(noisy, origin_lat=_PIN_LAT, origin_lng=_PIN_LNG)
    assert area_m2 == pytest.approx(429.0, rel=0.05)
    assert len(rect) == 5


def test_regularize_polygon_rejects_degenerate_ring():
    with pytest.raises(RoofSegmentationError):
        regularize_polygon(
            [(_PIN_LAT, _PIN_LNG), (_PIN_LAT, _PIN_LNG)],
            origin_lat=_PIN_LAT,
            origin_lng=_PIN_LNG,
        )


# ────────────────────────────────────────────────────────────────────
# Edge-alignment confidence
# ────────────────────────────────────────────────────────────────────
def test_edge_alignment_zero_for_uniform_image():
    """A flat image has zero gradient, so confidence is 0."""
    arr = np.full((128, 128), 0.5, dtype=np.float32)
    img_bytes = _png_bytes_from_array(arr)
    ring = _square_around(_PIN_LAT, _PIN_LNG, 0.00005)
    score = edge_alignment_confidence(
        ring,
        img_bytes,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=64,
        scale=2,
        zoom=20,
    )
    assert score == 0.0


def test_edge_alignment_high_for_polygon_on_image_step():
    """A polygon whose edges trace a synthetic dark-square boundary scores high."""
    # 200×200 image with a dark central square 100×100 — boundary at
    # rows/cols 50 and 149.
    arr = np.full((200, 200), 0.9, dtype=np.float32)
    arr[50:150, 50:150] = 0.1
    img_bytes = _png_bytes_from_array(arr)

    # Choose tile geometry so the central 100×100 square corresponds to
    # a real-world rectangle around the pin.
    image_size_px = 200
    scale = 1
    zoom = 20
    from app.services.gmaps_static import meters_per_pixel as _mpp

    mpp = _mpp(_PIN_LAT, zoom, scale)
    half_side_m = 50 * mpp  # 50 px from image centre
    half_side_lat = half_side_m / (math.radians(1.0) * 6_378_137.0)
    half_side_lng = half_side_m / (
        math.cos(math.radians(_PIN_LAT)) * math.radians(1.0) * 6_378_137.0
    )
    ring = [
        (_PIN_LAT - half_side_lat, _PIN_LNG - half_side_lng),
        (_PIN_LAT - half_side_lat, _PIN_LNG + half_side_lng),
        (_PIN_LAT + half_side_lat, _PIN_LNG + half_side_lng),
        (_PIN_LAT + half_side_lat, _PIN_LNG - half_side_lng),
        (_PIN_LAT - half_side_lat, _PIN_LNG - half_side_lng),
    ]
    score = edge_alignment_confidence(
        ring,
        img_bytes,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=image_size_px,
        scale=scale,
        zoom=zoom,
    )
    assert 0.5 < score <= 1.0


def test_edge_alignment_zero_for_polygon_outside_image():
    """A polygon entirely outside the tile contributes no in-image pixels."""
    arr = np.zeros((64, 64), dtype=np.float32)
    arr[20:40, 20:40] = 1.0
    img_bytes = _png_bytes_from_array(arr)
    far_pin_lat = _PIN_LAT + 0.05  # ~5.5 km north — well outside the tile.
    ring = _square_around(far_pin_lat, _PIN_LNG, 0.00005)
    score = edge_alignment_confidence(
        ring,
        img_bytes,
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=32,
        scale=2,
        zoom=20,
    )
    assert score == 0.0


# ────────────────────────────────────────────────────────────────────
# Public refine_polygon orchestrator
# ────────────────────────────────────────────────────────────────────
def test_refine_polygon_no_image_returns_zero_confidence():
    ring = _square_around(_PIN_LAT, _PIN_LNG)
    result = refine_polygon(
        ring, origin_lat=_PIN_LAT, origin_lng=_PIN_LNG, image_bytes=None
    )
    assert isinstance(result, RefinementResult)
    assert result.confidence == settings.cv_no_image_confidence
    assert result.area_m2 == pytest.approx(429.0, rel=0.05)
    assert any("no satellite imagery" in n for n in result.notes)


def test_refine_polygon_requires_geometry_when_image_provided():
    ring = _square_around(_PIN_LAT, _PIN_LNG)
    arr = np.full((32, 32), 0.5, dtype=np.float32)
    with pytest.raises(RoofSegmentationError):
        refine_polygon(
            ring,
            origin_lat=_PIN_LAT,
            origin_lng=_PIN_LNG,
            image_bytes=_png_bytes_from_array(arr),
        )


def test_refine_polygon_with_uniform_image_yields_low_confidence():
    ring = _square_around(_PIN_LAT, _PIN_LNG)
    arr = np.full((128, 128), 0.5, dtype=np.float32)
    result = refine_polygon(
        ring,
        origin_lat=_PIN_LAT,
        origin_lng=_PIN_LNG,
        image_bytes=_png_bytes_from_array(arr),
        centre_lat=_PIN_LAT,
        centre_lng=_PIN_LNG,
        image_size_px=64,
        scale=2,
        zoom=20,
    )
    assert result.confidence < 0.1
    assert result.area_m2 > 0
    assert len(result.polygon_lat_lng) == 5  # closed rectangle


def test_refinement_result_is_immutable():
    """The refinement output is a frozen dataclass — accidental mutation is rejected."""
    result = roof_segmentation.RefinementResult(
        polygon_lat_lng=[(0.0, 0.0)] * 4,
        area_m2=10.0,
        confidence=0.5,
        notes=[],
    )
    with pytest.raises((AttributeError, TypeError)):
        result.confidence = 0.9  # type: ignore[misc]
