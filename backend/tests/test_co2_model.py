"""Tests for the CO₂ avoidance kernel.

The expectations are derived against closed-form simplifications
(zero degradation, single-year horizon, etc.) so any failure points
straight at a regression in the math, not at a stale assumption.
"""
from __future__ import annotations

import math

import pytest

from app.config import settings
from app.schemas.co2 import CO2Request
from app.services import co2_model


def _zeroed_request(**overrides) -> CO2Request:
    """A request with degradation zeroed and a fixed emission factor.

    With zero degradation every year delivers the same kWh and the
    lifetime CO₂ collapses to ``annual_kwh × emission_factor × years``.
    """
    base = {
        "annual_kwh": 8000.0,
        "analysis_period_years": 25,
        "annual_degradation_rate": 0.0,
        "grid_emission_factor_kg_per_kwh": 0.46,
    }
    base.update(overrides)
    return CO2Request(**base)


def test_year1_co2_is_generation_times_emission_factor():
    """Year-1 CO₂ avoided equals year-1 generation × emission factor."""
    result = co2_model.compute_co2_avoidance(_zeroed_request())
    assert result.annual_co2_avoided_year1_kg == pytest.approx(8000.0 * 0.46)


def test_lifetime_co2_with_zero_degradation_is_linear():
    """With zero degradation, lifetime CO₂ = year-1 CO₂ × analysis years."""
    result = co2_model.compute_co2_avoidance(_zeroed_request())
    expected = 8000.0 * 0.46 * 25
    assert result.lifetime_co2_avoided_kg == pytest.approx(expected)
    assert result.lifetime_co2_avoided_tonnes == pytest.approx(expected / 1000.0)


def test_lifetime_co2_with_nonzero_degradation_is_geometric_series():
    """With degradation d, lifetime CO₂ is the closed-form geometric sum."""
    request = _zeroed_request(annual_degradation_rate=0.005)
    result = co2_model.compute_co2_avoidance(request)
    # Sum_{t=0..24} (1-d)^t = (1 - (1-d)^25) / d
    d = 0.005
    factor = (1.0 - (1.0 - d) ** 25) / d
    expected = 8000.0 * 0.46 * factor
    assert result.lifetime_co2_avoided_kg == pytest.approx(expected, rel=1e-9)


def test_annual_series_length_matches_analysis_horizon():
    """The year-by-year series must have exactly analysis_period_years entries."""
    result = co2_model.compute_co2_avoidance(_zeroed_request(analysis_period_years=10))
    assert len(result.annual_series) == 10
    # And the cumulative trajectory has one extra entry for year 0.
    assert len(result.cumulative_co2_avoided_kg) == 11


def test_cumulative_trajectory_starts_at_zero_and_is_monotonic():
    """Cumulative CO₂ is non-decreasing and starts at zero."""
    result = co2_model.compute_co2_avoidance(_zeroed_request(annual_degradation_rate=0.005))
    cum = result.cumulative_co2_avoided_kg
    assert cum[0] == 0.0
    for previous, current in zip(cum, cum[1:]):
        assert current >= previous
    assert cum[-1] == pytest.approx(result.lifetime_co2_avoided_kg)


def test_annual_series_year_indexing_is_one_based():
    """First yearly point must carry year=1, last must carry year=N."""
    result = co2_model.compute_co2_avoidance(_zeroed_request(analysis_period_years=10))
    assert result.annual_series[0].year == 1
    assert result.annual_series[-1].year == 10


def test_yearly_co2_decreases_under_degradation():
    """With non-zero degradation, each year's CO₂ should be strictly smaller."""
    result = co2_model.compute_co2_avoidance(_zeroed_request(annual_degradation_rate=0.01))
    for previous, current in zip(result.annual_series, result.annual_series[1:]):
        assert current.co2_avoided_kg < previous.co2_avoided_kg


def test_equivalents_use_published_factors():
    """Equivalents are direct ratios using the configured EPA constants."""
    result = co2_model.compute_co2_avoidance(_zeroed_request())
    lifetime = result.lifetime_co2_avoided_kg
    assert result.equivalents.equivalent_passenger_car_km == pytest.approx(
        lifetime / settings.co2_kg_per_passenger_car_km
    )
    assert result.equivalents.equivalent_petrol_litres == pytest.approx(
        lifetime / settings.co2_kg_per_petrol_litre
    )
    expected_tree_horizon = settings.co2_kg_per_tree_grown_year * 25
    assert result.equivalents.equivalent_urban_trees_grown == pytest.approx(
        lifetime / expected_tree_horizon
    )


def test_defaults_pull_from_settings():
    """Omitting overrides must fall through to the configured Egypt defaults."""
    result = co2_model.compute_co2_avoidance(CO2Request(annual_kwh=8000.0))
    assert result.analysis_period_years == settings.analysis_period_years
    assert result.annual_degradation_rate == settings.annual_degradation_rate
    assert (
        result.grid_emission_factor_kg_per_kwh
        == settings.egypt_grid_emission_kg_per_kwh
    )


def test_egypt_default_lifetime_is_in_published_band():
    """Sanity check: a typical 5-kW Egyptian system avoids ~70–110 t CO₂.

    Egyptian PV pre-feasibility studies report lifetime CO₂ avoidance
    in the 60–120 t band for 5-kW residential systems at the EEHC
    factor; an 8 000 kWh/yr year-1 figure (roughly 5 kWp Cairo PR) at
    the configured 0.46 kg/kWh and 0.5 %/yr degradation lands inside
    this band.
    """
    result = co2_model.compute_co2_avoidance(CO2Request(annual_kwh=8000.0))
    tonnes = result.lifetime_co2_avoided_tonnes
    assert 60.0 < tonnes < 120.0


def test_emission_factor_zero_yields_zero_co2():
    """Setting emission factor to zero must zero the entire output."""
    request = _zeroed_request(grid_emission_factor_kg_per_kwh=0.0)
    result = co2_model.compute_co2_avoidance(request)
    assert result.lifetime_co2_avoided_kg == 0.0
    assert result.annual_co2_avoided_year1_kg == 0.0
    assert all(p.co2_avoided_kg == 0.0 for p in result.annual_series)
    assert result.equivalents.equivalent_passenger_car_km == 0.0
    assert result.equivalents.equivalent_petrol_litres == 0.0
    assert result.equivalents.equivalent_urban_trees_grown == 0.0


def test_overrides_are_echoed_in_response():
    """Every echoed assumption must reflect the request, not the defaults."""
    request = _zeroed_request(
        analysis_period_years=12,
        annual_degradation_rate=0.007,
        grid_emission_factor_kg_per_kwh=0.40,
    )
    result = co2_model.compute_co2_avoidance(request)
    assert result.analysis_period_years == 12
    assert result.annual_degradation_rate == 0.007
    assert result.grid_emission_factor_kg_per_kwh == 0.40
    assert result.annual_kwh == 8000.0


def test_zero_kwh_request_is_rejected_at_schema_layer():
    """Pydantic must reject annual_kwh <= 0 (gt=0)."""
    with pytest.raises(ValueError):
        CO2Request(annual_kwh=0.0)


def test_negative_emission_factor_rejected_at_schema_layer():
    """Pydantic must reject a negative emission factor (ge=0)."""
    with pytest.raises(ValueError):
        CO2Request(annual_kwh=8000.0, grid_emission_factor_kg_per_kwh=-0.1)
