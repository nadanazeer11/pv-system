"""Unit tests for the Day-11 tilt and azimuth estimators."""
from __future__ import annotations

import math

import pytest

from app.config import settings
from app.services import roof_orientation
from app.services.roof_orientation import (
    AzimuthEstimate,
    TiltEstimate,
    estimate_azimuth,
    estimate_tilt,
    is_flat_roof,
    polygon_area_m2,
)


_CAIRO_LAT = 30.0444
_CAIRO_LNG = 31.2357


# ────────────────────────────────────────────────────────────────────
# Tilt
# ────────────────────────────────────────────────────────────────────
def test_estimate_tilt_uses_roof_angle_when_present():
    estimate = estimate_tilt({"roof:angle": "27"}, latitude=_CAIRO_LAT)
    assert estimate == TiltEstimate(tilt_deg=27.0, source="osm:roof:angle")


def test_estimate_tilt_ignores_out_of_range_roof_angle():
    estimate = estimate_tilt({"roof:angle": "85"}, latitude=_CAIRO_LAT)
    # 85° is out of band, so the estimator must fall through to defaults.
    assert estimate.source != "osm:roof:angle"


def test_estimate_tilt_ignores_unparseable_roof_angle():
    estimate = estimate_tilt({"roof:angle": "steep"}, latitude=_CAIRO_LAT)
    assert estimate.source != "osm:roof:angle"


def test_estimate_tilt_flat_shape_uses_latitude_optimum():
    estimate = estimate_tilt({"roof:shape": "flat"}, latitude=_CAIRO_LAT)
    assert estimate.tilt_deg == pytest.approx(_CAIRO_LAT)
    assert estimate.source == "flat-roof-default-cairo-optimum"


def test_estimate_tilt_pitched_shape_uses_pitched_default():
    estimate = estimate_tilt({"roof:shape": "gabled"}, latitude=_CAIRO_LAT)
    assert estimate.tilt_deg == pytest.approx(settings.cv_default_pitched_roof_tilt_deg)
    assert estimate.source == "osm:roof:shape"


def test_estimate_tilt_shed_shape_uses_shed_default():
    estimate = estimate_tilt({"roof:shape": "shed"}, latitude=_CAIRO_LAT)
    assert estimate.tilt_deg == pytest.approx(settings.cv_default_shed_roof_tilt_deg)
    assert estimate.source == "osm:roof:shape"


def test_estimate_tilt_no_tags_falls_back_to_latitude():
    estimate = estimate_tilt(None, latitude=_CAIRO_LAT)
    assert estimate.tilt_deg == pytest.approx(_CAIRO_LAT)
    assert estimate.source == "fallback-cairo-default"


def test_estimate_tilt_negative_latitude_uses_absolute_value():
    estimate = estimate_tilt({"roof:shape": "flat"}, latitude=-30.0)
    assert estimate.tilt_deg == pytest.approx(30.0)


def test_estimate_tilt_unknown_shape_falls_back_to_latitude():
    estimate = estimate_tilt({"roof:shape": "spaceship"}, latitude=_CAIRO_LAT)
    assert estimate.tilt_deg == pytest.approx(_CAIRO_LAT)
    assert estimate.source == "fallback-cairo-default"


# ────────────────────────────────────────────────────────────────────
# is_flat_roof
# ────────────────────────────────────────────────────────────────────
def test_is_flat_roof_true_for_no_tags():
    assert is_flat_roof(None) is True
    assert is_flat_roof({}) is True


def test_is_flat_roof_true_for_explicit_flat():
    assert is_flat_roof({"roof:shape": "flat"}) is True


def test_is_flat_roof_false_for_pitched_shape():
    assert is_flat_roof({"roof:shape": "gabled"}) is False
    assert is_flat_roof({"roof:shape": "hipped"}) is False


def test_is_flat_roof_false_when_roof_angle_above_threshold():
    assert is_flat_roof({"roof:angle": "27"}) is False


def test_is_flat_roof_true_when_roof_angle_is_zero():
    assert is_flat_roof({"roof:angle": "0"}) is True


# ────────────────────────────────────────────────────────────────────
# Azimuth
# ────────────────────────────────────────────────────────────────────
def _polygon_axis_aligned() -> list[tuple[float, float]]:
    """Square aligned to the cardinal axes."""
    h = 0.0001
    return [
        (_CAIRO_LAT - h, _CAIRO_LNG - h),
        (_CAIRO_LAT - h, _CAIRO_LNG + h),
        (_CAIRO_LAT + h, _CAIRO_LNG + h),
        (_CAIRO_LAT + h, _CAIRO_LNG - h),
        (_CAIRO_LAT - h, _CAIRO_LNG - h),
    ]


def _polygon_long_east_west() -> list[tuple[float, float]]:
    """Rectangle 4× longer east-west than north-south, axis-aligned.

    Long edge bearing is 90° (east). Panels should face south = 180°.
    """
    h_lat = 0.00002  # 2.2 m
    h_lng = 0.00010  # ~9.6 m
    return [
        (_CAIRO_LAT - h_lat, _CAIRO_LNG - h_lng),
        (_CAIRO_LAT - h_lat, _CAIRO_LNG + h_lng),
        (_CAIRO_LAT + h_lat, _CAIRO_LNG + h_lng),
        (_CAIRO_LAT + h_lat, _CAIRO_LNG - h_lng),
        (_CAIRO_LAT - h_lat, _CAIRO_LNG - h_lng),
    ]


def _polygon_rotated_45() -> list[tuple[float, float]]:
    """Diamond — a square rotated 45°. Long-edge bearing is ~45°.

    Panels would face perpendicular to the long edge closest to south:
    perpendicular candidates are 135° and 315°; 135° is closer to 180°.
    """
    h = 0.0001
    return [
        (_CAIRO_LAT, _CAIRO_LNG - h),
        (_CAIRO_LAT - h, _CAIRO_LNG),
        (_CAIRO_LAT, _CAIRO_LNG + h),
        (_CAIRO_LAT + h, _CAIRO_LNG),
        (_CAIRO_LAT, _CAIRO_LNG - h),
    ]


def test_estimate_azimuth_flat_roof_returns_south():
    estimate = estimate_azimuth(_polygon_long_east_west(), is_flat_roof=True)
    assert estimate == AzimuthEstimate(azimuth_deg=180.0, source="fallback-south")


def test_estimate_azimuth_pitched_long_east_west_faces_south():
    estimate = estimate_azimuth(
        _polygon_long_east_west(),
        is_flat_roof=False,
        fallback_deg=180.0,
    )
    # Long edge ≈ 90°, perpendicular toward south = 180° → snapped.
    assert estimate.azimuth_deg == pytest.approx(180.0, abs=settings.cv_azimuth_snap_tolerance_deg)
    assert estimate.source.startswith("polygon-long-edge")


def test_estimate_azimuth_axis_aligned_square_snaps_to_cardinal():
    estimate = estimate_azimuth(
        _polygon_axis_aligned(),
        is_flat_roof=False,
        fallback_deg=180.0,
    )
    # Either 90° or 0° long edge (both equal length); panel azimuth is
    # 180° in either case (south-facing perpendicular). With snap we
    # land exactly on a cardinal.
    assert estimate.azimuth_deg in {0.0, 90.0, 180.0, 270.0}
    assert "snapped-cardinal" in estimate.source


def test_estimate_azimuth_rotated_45_does_not_snap():
    estimate = estimate_azimuth(
        _polygon_rotated_45(),
        is_flat_roof=False,
        fallback_deg=180.0,
    )
    # Long edge bearing ~45° → panel azimuth ~135°, far from any cardinal.
    assert 100.0 < estimate.azimuth_deg < 230.0
    assert estimate.azimuth_deg not in {0.0, 90.0, 180.0, 270.0}
    assert estimate.source == "polygon-long-edge"


def test_estimate_azimuth_no_polygon_returns_fallback():
    estimate = estimate_azimuth(None, is_flat_roof=False, fallback_deg=180.0)
    assert estimate == AzimuthEstimate(azimuth_deg=180.0, source="fallback-south")


def test_estimate_azimuth_too_few_points_returns_fallback():
    estimate = estimate_azimuth(
        [(_CAIRO_LAT, _CAIRO_LNG)], is_flat_roof=False, fallback_deg=180.0
    )
    assert estimate.source == "fallback-south"


def test_estimate_azimuth_returns_value_in_range():
    """The azimuth returned must always be a valid bearing in [0, 360)."""
    polygons = [
        _polygon_axis_aligned(),
        _polygon_long_east_west(),
        _polygon_rotated_45(),
    ]
    for polygon in polygons:
        estimate = estimate_azimuth(polygon, is_flat_roof=False)
        assert 0.0 <= estimate.azimuth_deg < 360.0


def test_estimate_azimuth_fallback_normalised_into_range():
    estimate = estimate_azimuth(None, is_flat_roof=True, fallback_deg=540.0)
    assert estimate.azimuth_deg == pytest.approx(180.0)


# ────────────────────────────────────────────────────────────────────
# polygon_area_m2 helper
# ────────────────────────────────────────────────────────────────────
def test_polygon_area_m2_for_known_square():
    ring = _polygon_axis_aligned()
    area = polygon_area_m2(ring, _CAIRO_LAT, _CAIRO_LNG)
    # Same 22.26 × 19.28 m square used elsewhere in the suite.
    assert area == pytest.approx(429.0, rel=0.05)


def test_polygon_area_m2_buffers_invalid_self_intersecting_ring():
    """Self-intersecting (bowtie) polygon should still yield a finite area."""
    ring = [
        (_CAIRO_LAT, _CAIRO_LNG),
        (_CAIRO_LAT + 0.0001, _CAIRO_LNG + 0.0001),
        (_CAIRO_LAT, _CAIRO_LNG + 0.0001),
        (_CAIRO_LAT + 0.0001, _CAIRO_LNG),
        (_CAIRO_LAT, _CAIRO_LNG),
    ]
    area = polygon_area_m2(ring, _CAIRO_LAT, _CAIRO_LNG)
    assert math.isfinite(area)
    assert area >= 0.0
