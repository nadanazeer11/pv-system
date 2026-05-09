"""Tests for the inter-row spacing service.

Numerical expectations are derived by hand against the Egypt-tuned
defaults in :pydata:`app.config.settings` (1.8 m slope height, 26° tilt,
22° design sun) so a failing test points squarely at a regression in
the math, not at a stale assumption.

Reference values
----------------
With the defaults::

    footprint = 1.8 × cos(26°) = 1.6178 m
    shadow    = 1.8 × sin(26°) / tan(22°) = 1.9534 m
    pitch     = 3.5712 m
    density   = 0.4530
"""
import math

import pytest

from app.config import settings
from app.schemas.shading import InterRowSpacingRequest
from app.services import shading


def test_default_geometry_matches_hand_derivation():
    """1.8 m × 26° tilt × 22° sun → pitch ≈ 3.57 m, density ≈ 0.45."""
    result = shading.compute_inter_row_spacing(InterRowSpacingRequest())

    assert result.panel_footprint_m == pytest.approx(1.8 * math.cos(math.radians(26)))
    assert result.shadow_length_m == pytest.approx(
        1.8 * math.sin(math.radians(26)) / math.tan(math.radians(22))
    )
    assert result.row_pitch_m == pytest.approx(3.5712, abs=1e-3)
    assert result.inter_row_density_factor == pytest.approx(0.4530, abs=1e-3)
    # Echoed assumptions match config defaults
    assert result.panel_slope_height_m == settings.panel_slope_height_m
    assert result.tilt_deg == settings.default_tilt_deg
    assert result.sun_elevation_deg == settings.design_sun_elevation_deg


def test_density_times_pitch_equals_footprint():
    """Math invariant: density = footprint / pitch."""
    result = shading.compute_inter_row_spacing(
        InterRowSpacingRequest(tilt_deg=30, sun_elevation_deg=20)
    )
    assert result.inter_row_density_factor * result.row_pitch_m == pytest.approx(
        result.panel_footprint_m
    )


def test_flat_panels_have_unit_density_and_zero_shadow():
    """Tilt = 0 → no inter-row shadow → density collapses to exactly 1."""
    result = shading.compute_inter_row_spacing(InterRowSpacingRequest(tilt_deg=0))

    assert result.shadow_length_m == 0.0
    assert result.inter_row_density_factor == 1.0
    assert result.row_pitch_m == result.panel_footprint_m
    assert result.panel_footprint_m == pytest.approx(settings.panel_slope_height_m)


def test_higher_tilt_widens_pitch_and_lowers_density():
    """A steeper panel casts a longer shadow → wider pitch → lower density."""
    low = shading.compute_inter_row_spacing(InterRowSpacingRequest(tilt_deg=15))
    high = shading.compute_inter_row_spacing(InterRowSpacingRequest(tilt_deg=45))

    assert high.row_pitch_m > low.row_pitch_m
    assert high.inter_row_density_factor < low.inter_row_density_factor


def test_higher_sun_elevation_narrows_pitch_and_raises_density():
    """A higher sun → shorter shadow → narrower pitch → higher density."""
    morning = shading.compute_inter_row_spacing(
        InterRowSpacingRequest(sun_elevation_deg=22)
    )
    noon = shading.compute_inter_row_spacing(
        InterRowSpacingRequest(sun_elevation_deg=60)
    )

    assert noon.row_pitch_m < morning.row_pitch_m
    assert noon.inter_row_density_factor > morning.inter_row_density_factor


def test_overrides_shadow_config_defaults():
    """Per-request overrides must take precedence over config."""
    result = shading.compute_inter_row_spacing(
        InterRowSpacingRequest(
            panel_slope_height_m=2.0,
            tilt_deg=30,
            sun_elevation_deg=30,
        )
    )

    expected_footprint = 2.0 * math.cos(math.radians(30))
    expected_shadow = 2.0 * math.sin(math.radians(30)) / math.tan(math.radians(30))
    assert result.panel_footprint_m == pytest.approx(expected_footprint)
    assert result.shadow_length_m == pytest.approx(expected_shadow)
    assert result.panel_slope_height_m == 2.0
    assert result.tilt_deg == 30
    assert result.sun_elevation_deg == 30


def test_panel_height_scales_pitch_linearly():
    """Doubling the panel height must double every linear length but leave the density unchanged."""
    one = shading.compute_inter_row_spacing(
        InterRowSpacingRequest(panel_slope_height_m=1.0)
    )
    two = shading.compute_inter_row_spacing(
        InterRowSpacingRequest(panel_slope_height_m=2.0)
    )

    assert two.row_pitch_m == pytest.approx(2 * one.row_pitch_m)
    assert two.shadow_length_m == pytest.approx(2 * one.shadow_length_m)
    assert two.panel_footprint_m == pytest.approx(2 * one.panel_footprint_m)
    # Density is dimensionless — it depends on tilt and sun, not size.
    assert two.inter_row_density_factor == pytest.approx(one.inter_row_density_factor)


def test_density_is_bounded_by_zero_and_one():
    """For any physically valid input the density factor lies in (0, 1]."""
    for tilt in (5, 26, 45, 60, 80):
        for sun in (5, 22, 45, 80):
            result = shading.compute_inter_row_spacing(
                InterRowSpacingRequest(tilt_deg=tilt, sun_elevation_deg=sun)
            )
            assert 0 < result.inter_row_density_factor <= 1


def test_request_rejects_out_of_range_inputs():
    """Pydantic must enforce the physical bounds at the schema layer."""
    from pydantic import ValidationError

    # Panel height must be positive
    with pytest.raises(ValidationError):
        InterRowSpacingRequest(panel_slope_height_m=0)
    # Tilt cannot be ≥ 90° (panel would be vertical or pointing back)
    with pytest.raises(ValidationError):
        InterRowSpacingRequest(tilt_deg=90)
    with pytest.raises(ValidationError):
        InterRowSpacingRequest(tilt_deg=-1)
    # Sun must be above the horizon — 0° elevation gives infinite shadow
    with pytest.raises(ValidationError):
        InterRowSpacingRequest(sun_elevation_deg=0)
    with pytest.raises(ValidationError):
        InterRowSpacingRequest(sun_elevation_deg=91)


def test_unit_panel_matches_published_rule_of_thumb():
    """Sanity-check against the published "row pitch ≈ 2 × panel length"
    rule for portrait-mounted PV at mid-latitudes."""
    # 1.0 m panel at 26° tilt, 22° sun → pitch ≈ 1.98 m ≈ 2 × panel.
    result = shading.compute_inter_row_spacing(
        InterRowSpacingRequest(
            panel_slope_height_m=1.0, tilt_deg=26, sun_elevation_deg=22,
        )
    )
    assert result.row_pitch_m == pytest.approx(1.98, abs=0.05)
