"""Tests for the load-profile-driven sizing service.

Numerical expectations are derived by hand against the Egypt-tuned
defaults in app.config.settings (5.5 PSH, 0.78 PR, 450 W panels,
1.8 m², 0.7 utilization).
"""
import math

import pytest

from app.config import settings
from app.schemas.load_sizing import ApplianceEntry, LoadSizingRequest
from app.services import load_sizing


def test_appliance_library_is_non_empty():
    library = load_sizing.get_appliance_library()
    assert len(library) > 10
    # Every entry must look usable to the UI
    for entry in library:
        assert entry.watts > 0
        assert 0 < entry.typical_hours_per_day <= 24
        assert entry.category != ""


def test_compute_load_sizing_one_appliance_known_arithmetic():
    """1000 W × 5 h = 5 kWh/day. system_kw = 5 / (5.5 × 0.78) ≈ 1.166."""
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="Test", watts=1000, hours_per_day=5, quantity=1)],
    )
    result = load_sizing.compute_load_sizing(request)

    assert result.daily_load_kwh == pytest.approx(5.0)
    assert result.peak_load_kw == pytest.approx(1.0)
    assert result.monthly_load_kwh == pytest.approx(5.0 * 30.4)
    assert result.annual_load_kwh == pytest.approx(5.0 * 365)

    raw_system_kw = 5.0 / (settings.egypt_peak_sun_hours * settings.system_performance_ratio)
    expected_panels = math.ceil(raw_system_kw / (settings.panel_rated_watts / 1000.0))
    assert result.recommended_panel_count == expected_panels
    assert result.recommended_system_kw == pytest.approx(
        expected_panels * settings.panel_rated_watts / 1000.0
    )


def test_quantity_multiplies_load():
    """quantity=3 must triple both daily energy and peak draw."""
    one = load_sizing.compute_load_sizing(
        LoadSizingRequest(appliances=[ApplianceEntry(name="x", watts=500, hours_per_day=4, quantity=1)])
    )
    three = load_sizing.compute_load_sizing(
        LoadSizingRequest(appliances=[ApplianceEntry(name="x", watts=500, hours_per_day=4, quantity=3)])
    )
    assert three.daily_load_kwh == pytest.approx(3 * one.daily_load_kwh)
    assert three.peak_load_kw == pytest.approx(3 * one.peak_load_kw)


def test_coverage_fraction_scales_recommendation():
    """At coverage=0.5 the system covers half the load — daily load is unchanged."""
    full = load_sizing.compute_load_sizing(
        LoadSizingRequest(
            appliances=[ApplianceEntry(name="x", watts=2000, hours_per_day=4, quantity=1)],
            coverage_fraction=1.0,
        )
    )
    half = load_sizing.compute_load_sizing(
        LoadSizingRequest(
            appliances=[ApplianceEntry(name="x", watts=2000, hours_per_day=4, quantity=1)],
            coverage_fraction=0.5,
        )
    )
    assert full.daily_load_kwh == pytest.approx(half.daily_load_kwh)
    # The half-coverage system should be roughly half the size; allow a
    # one-panel tolerance because the panel-snap rounds up.
    panel_kw = settings.panel_rated_watts / 1000.0
    assert half.recommended_system_kw <= full.recommended_system_kw / 2 + panel_kw


def test_panel_count_rounds_up_to_meet_load():
    """Sizing for a load must never under-provision — panel count rounds UP."""
    # Pick a load that lands between two panel counts.
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="x", watts=1000, hours_per_day=5, quantity=1)],
    )
    result = load_sizing.compute_load_sizing(request)
    panel_kw = settings.panel_rated_watts / 1000.0
    raw_kw = result.daily_load_kwh / (settings.egypt_peak_sun_hours * settings.system_performance_ratio)
    # Floor would under-provision; service must use ceil.
    assert result.recommended_panel_count >= math.ceil(raw_kw / panel_kw)


def test_required_roof_area_consistent_with_sizing_inverse():
    """required_roof_area * utilization / panel_area should equal panel_count."""
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="AC", watts=1500, hours_per_day=6, quantity=2)],
    )
    result = load_sizing.compute_load_sizing(request)
    derived = result.required_roof_area_m2 * result.roof_utilization_factor / result.panel_area_m2
    assert derived == pytest.approx(result.recommended_panel_count)


def test_roof_fits_when_available_area_is_large_enough():
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="x", watts=500, hours_per_day=2, quantity=1)],
        available_roof_area_m2=10_000,
    )
    result = load_sizing.compute_load_sizing(request)
    assert result.roof_fits is True
    assert result.roof_area_shortfall_m2 is None


def test_roof_does_not_fit_when_too_small():
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="AC", watts=2200, hours_per_day=8, quantity=4)],
        available_roof_area_m2=5.0,
    )
    result = load_sizing.compute_load_sizing(request)
    assert result.roof_fits is False
    assert result.roof_area_shortfall_m2 is not None
    assert result.roof_area_shortfall_m2 > 0
    assert result.roof_area_shortfall_m2 == pytest.approx(
        result.required_roof_area_m2 - 5.0
    )


def test_roof_fit_unknown_when_area_omitted():
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="x", watts=500, hours_per_day=2, quantity=1)],
    )
    result = load_sizing.compute_load_sizing(request)
    assert result.roof_fits is None
    assert result.available_roof_area_m2 is None
    assert result.roof_area_shortfall_m2 is None


def test_zero_hours_raises_load_sizing_error():
    """Every appliance at hours_per_day=0 must be flagged, not silently sized to 0 kW."""
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="x", watts=1000, hours_per_day=0, quantity=1)],
    )
    with pytest.raises(load_sizing.LoadSizingError):
        load_sizing.compute_load_sizing(request)


def test_request_rejects_empty_appliance_list():
    """Pydantic must reject a load profile with no appliances at the schema layer."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LoadSizingRequest(appliances=[])


def test_appliance_entry_rejects_invalid_inputs():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ApplianceEntry(name="x", watts=0, hours_per_day=1, quantity=1)
    with pytest.raises(ValidationError):
        ApplianceEntry(name="x", watts=100, hours_per_day=25, quantity=1)
    with pytest.raises(ValidationError):
        ApplianceEntry(name="x", watts=100, hours_per_day=1, quantity=0)


def test_overrides_shadow_config_defaults():
    request = LoadSizingRequest(
        appliances=[ApplianceEntry(name="x", watts=1000, hours_per_day=5, quantity=1)],
        panel_rated_watts=600,
        panel_area_m2=2.4,
        roof_utilization_factor=0.5,
    )
    result = load_sizing.compute_load_sizing(request)
    assert result.panel_rated_watts == 600
    assert result.panel_area_m2 == 2.4
    assert result.roof_utilization_factor == 0.5
