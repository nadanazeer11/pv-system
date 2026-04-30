"""Tests for the PV sizing service.

Numerical expectations are derived by hand against the Egypt-tuned
defaults in app.config.settings (450 W panels, 1.8 m², 0.7 utilization)
so a failing test points squarely at a regression in the math, not at a
stale assumption.
"""
import pytest

from app.config import settings
from app.schemas.sizing import SizingRequest
from app.services import pv_sizing


def test_compute_system_size_with_defaults_known_roof():
    """100 m² roof × 0.7 = 70 m² usable; 70 / 1.8 = 38 panels (floor)."""
    result = pv_sizing.compute_system_size(SizingRequest(roof_area_m2=100.0))

    assert result.usable_roof_area_m2 == pytest.approx(70.0)
    assert result.panel_count == 38
    # 38 × 450 W = 17,100 W = 17.1 kW
    assert result.system_kw == pytest.approx(17.1)
    # Echoed assumptions match config defaults
    assert result.panel_rated_watts == settings.panel_rated_watts
    assert result.panel_area_m2 == settings.panel_area_m2
    assert result.roof_utilization_factor == settings.roof_utilization_factor


def test_compute_system_size_floors_panel_count():
    """Fractional panels must always round DOWN — never promise capacity
    the roof cannot physically hold."""
    # 50 m² × 0.7 = 35 m² usable; 35 / 1.8 = 19.444... -> 19 panels
    result = pv_sizing.compute_system_size(SizingRequest(roof_area_m2=50.0))

    assert result.panel_count == 19
    assert result.system_kw == pytest.approx(19 * 450 / 1000.0)


def test_compute_system_size_honours_overrides():
    """Per-request overrides shadow the config defaults."""
    result = pv_sizing.compute_system_size(
        SizingRequest(
            roof_area_m2=200.0,
            panel_rated_watts=600.0,
            panel_area_m2=2.4,
            roof_utilization_factor=0.5,
        )
    )

    # 200 × 0.5 = 100 m² usable; 100 / 2.4 = 41.66... -> 41 panels
    assert result.usable_roof_area_m2 == pytest.approx(100.0)
    assert result.panel_count == 41
    assert result.system_kw == pytest.approx(41 * 600 / 1000.0)
    assert result.panel_rated_watts == 600.0
    assert result.panel_area_m2 == 2.4
    assert result.roof_utilization_factor == 0.5


def test_compute_system_size_density_is_consistent():
    """panel_density should equal (system_w / usable_area)."""
    result = pv_sizing.compute_system_size(SizingRequest(roof_area_m2=100.0))

    expected_density = (result.panel_count * result.panel_rated_watts) / result.usable_roof_area_m2
    assert result.panel_density_w_per_m2 == pytest.approx(expected_density)


def test_compute_system_size_rejects_too_small_roof():
    """A roof smaller than one panel after utilization must be flagged
    explicitly rather than silently returning a 0 kW system."""
    # 2 m² × 0.7 = 1.4 m² usable, < 1.8 m² panel area
    with pytest.raises(pv_sizing.SizingError) as info:
        pv_sizing.compute_system_size(SizingRequest(roof_area_m2=2.0))
    assert "smaller than a single panel" in str(info.value)


def test_compute_system_size_exactly_one_panel():
    """Boundary: usable area exactly equals one panel area should yield
    exactly one panel, not zero."""
    # roof × 0.7 = 1.8  →  roof = 1.8 / 0.7
    boundary_area = settings.panel_area_m2 / settings.roof_utilization_factor
    result = pv_sizing.compute_system_size(SizingRequest(roof_area_m2=boundary_area))

    assert result.panel_count == 1
    assert result.system_kw == pytest.approx(settings.panel_rated_watts / 1000.0)


def test_sizing_request_rejects_non_positive_area():
    """Pydantic must enforce roof_area_m2 > 0 at the schema layer."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SizingRequest(roof_area_m2=0.0)
    with pytest.raises(ValidationError):
        SizingRequest(roof_area_m2=-10.0)


def test_sizing_request_rejects_utilization_above_one():
    """Utilization is a fraction in (0, 1] — values above 1 are nonsense
    (more usable area than the roof itself)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SizingRequest(roof_area_m2=100.0, roof_utilization_factor=1.5)
