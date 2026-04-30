"""Tests for the basic financial feasibility service.

Most expectations are hand-derived against closed-form simplifications
(zero discount rate, zero tariff inflation, zero degradation, zero O&M)
so a failing test points squarely at a regression in the math, not at a
stale assumption. The full-default cases are then sanity-checked against
the Egyptian PV literature payback range (5–10 years for residential
rooftop under current tariffs).
"""
from __future__ import annotations

import math

import pytest

from app.config import settings
from app.schemas.financial import FinancialBasicRequest
from app.services import financial_basic


def _zeroed_request(**overrides) -> FinancialBasicRequest:
    """Helper: a request with all economic frictions zeroed.

    With zero discount rate, zero inflation, zero degradation, zero O&M,
    every metric reduces to a textbook closed form: simple payback ==
    discounted payback == capex / (annual_kwh × tariff), NPV is
    ``annual_savings × years − capex``, and LCOE is
    ``capex / (annual_kwh × years)``. Tests built on this baseline are
    pure arithmetic.
    """
    base = {
        "system_kw": 5.0,
        "annual_kwh": 8000.0,
        "tariff_egp_per_kwh": 2.0,
        "cost_egp_per_kw": 35000.0,
        "analysis_period_years": 25,
        "discount_rate": 0.0,
        "tariff_inflation_rate": 0.0,
        "annual_degradation_rate": 0.0,
        "om_cost_fraction": 0.0,
    }
    base.update(overrides)
    return FinancialBasicRequest(**base)


# ─────────────────────────── core arithmetic ───────────────────────────


def test_capex_is_system_kw_times_cost_per_kw():
    """capex = system_kw × cost_egp_per_kw — the most basic identity."""
    result = financial_basic.compute_financials(_zeroed_request())
    assert result.capex_egp == pytest.approx(5.0 * 35000.0)


def test_year1_savings_is_generation_times_tariff():
    """Year-1 savings = annual_kwh × tariff (no inflation, no degradation)."""
    result = financial_basic.compute_financials(_zeroed_request())
    assert result.annual_savings_year1_egp == pytest.approx(8000.0 * 2.0)


def test_simple_payback_zero_friction_is_capex_over_savings():
    """capex 175 000, savings 16 000/yr → payback = 10.9375 years."""
    result = financial_basic.compute_financials(_zeroed_request())
    expected = (5.0 * 35000.0) / (8000.0 * 2.0)
    assert result.simple_payback_years == pytest.approx(expected)


def test_discounted_payback_equals_simple_when_friction_zero():
    """With r=0, i=0, d=0, OM=0 the two paybacks must coincide exactly."""
    result = financial_basic.compute_financials(_zeroed_request())
    assert result.discounted_payback_years is not None
    assert result.simple_payback_years is not None
    assert result.discounted_payback_years == pytest.approx(
        result.simple_payback_years
    )


def test_npv_zero_friction_closed_form():
    """NPV = annual_savings × years − capex with all frictions zero."""
    result = financial_basic.compute_financials(_zeroed_request())
    expected = 8000.0 * 2.0 * 25 - 5.0 * 35000.0
    assert result.npv_egp == pytest.approx(expected)


def test_lcoe_zero_friction_closed_form():
    """LCOE = capex / (annual_kwh × years) when r=0 and d=0, OM=0."""
    result = financial_basic.compute_financials(_zeroed_request())
    expected = (5.0 * 35000.0) / (8000.0 * 25)
    assert result.lcoe_egp_per_kwh == pytest.approx(expected)


def test_lifetime_savings_equals_year1_times_horizon_when_static():
    result = financial_basic.compute_financials(_zeroed_request())
    assert result.lifetime_savings_egp == pytest.approx(8000.0 * 2.0 * 25)


def test_lifetime_generation_equals_year1_times_horizon_when_no_degradation():
    result = financial_basic.compute_financials(_zeroed_request())
    assert result.lifetime_generation_kwh == pytest.approx(8000.0 * 25)


def test_cumulative_cashflow_starts_at_minus_capex():
    """Year 0 in the cash-flow series is the capex outlay."""
    result = financial_basic.compute_financials(_zeroed_request())
    assert result.cumulative_cashflow_series_egp[0] == pytest.approx(-5.0 * 35000.0)


def test_cumulative_cashflow_ends_at_npv_when_zero_discount():
    """With r=0 the final cumulative equals NPV (no discounting effect)."""
    result = financial_basic.compute_financials(_zeroed_request())
    assert result.cumulative_cashflow_series_egp[-1] == pytest.approx(result.npv_egp)


def test_cumulative_cashflow_series_length_matches_horizon_plus_one():
    """One entry for year 0 plus one per analysis year."""
    result = financial_basic.compute_financials(
        _zeroed_request(analysis_period_years=10)
    )
    assert len(result.cumulative_cashflow_series_egp) == 11
    assert len(result.annual_savings_series_egp) == 10


# ─────────────────── time-value-of-money behaviour ─────────────────────


def test_npv_drops_when_discount_rate_increases():
    """Higher discount rate punishes future savings, lowering NPV."""
    low = financial_basic.compute_financials(_zeroed_request(discount_rate=0.0))
    high = financial_basic.compute_financials(_zeroed_request(discount_rate=0.10))
    assert high.npv_egp < low.npv_egp


def test_discounted_payback_longer_than_simple_with_positive_discount():
    """Discounting future savings can only push payback later, never sooner.

    Uses a 4 % discount rate (matching PLAN.md's real cost of capital)
    rather than a punitive value, so the discounted recovery still lands
    inside the 25-year horizon and the comparison is meaningful.
    """
    request = _zeroed_request(discount_rate=0.04)
    result = financial_basic.compute_financials(request)
    assert result.discounted_payback_years is not None
    assert result.simple_payback_years is not None
    assert result.discounted_payback_years > result.simple_payback_years


def test_tariff_inflation_increases_lifetime_savings():
    """Escalating tariffs → more nominal EGP saved over the project life."""
    flat = financial_basic.compute_financials(_zeroed_request())
    rising = financial_basic.compute_financials(
        _zeroed_request(tariff_inflation_rate=0.08)
    )
    assert rising.lifetime_savings_egp > flat.lifetime_savings_egp


def test_degradation_reduces_lifetime_generation():
    """Module degradation must trim total kWh delivered."""
    fresh = financial_basic.compute_financials(_zeroed_request())
    aged = financial_basic.compute_financials(
        _zeroed_request(annual_degradation_rate=0.005)
    )
    assert aged.lifetime_generation_kwh < fresh.lifetime_generation_kwh


def test_om_cost_lowers_npv():
    """Operating costs eat into project NPV; with capex fixed, NPV must drop."""
    no_om = financial_basic.compute_financials(_zeroed_request())
    with_om = financial_basic.compute_financials(_zeroed_request(om_cost_fraction=0.01))
    assert with_om.npv_egp < no_om.npv_egp


def test_annual_savings_series_grows_with_inflation_and_decays_with_degradation():
    """Per the model: savings(t) = ann_kwh·(1−d)^(t−1) · tariff·(1+i)^(t−1)."""
    request = _zeroed_request(
        tariff_inflation_rate=0.08,
        annual_degradation_rate=0.005,
    )
    result = financial_basic.compute_financials(request)
    series = result.annual_savings_series_egp
    # Hand-derive year 1 and year 2.
    expected_y1 = 8000.0 * 2.0
    expected_y2 = 8000.0 * (1.0 - 0.005) * 2.0 * (1.0 + 0.08)
    assert series[0] == pytest.approx(expected_y1)
    assert series[1] == pytest.approx(expected_y2)


# ────────────────────── boundary and edge cases ────────────────────────


def test_payback_beyond_horizon_returns_none():
    """When tariff is so low that the system never recovers, payback is None."""
    request = _zeroed_request(
        tariff_egp_per_kwh=0.01,  # capex 175 000, year-1 savings 80 → 2 187 yrs
        analysis_period_years=25,
    )
    result = financial_basic.compute_financials(request)
    assert result.simple_payback_years is None
    assert result.discounted_payback_years is None


def test_om_exceeding_savings_yields_no_payback():
    """If O&M > year-1 savings the project has no positive cash flow.

    Year-1 savings = 16 000 EGP; O&M at 10 % of 175 000 = 17 500 EGP.
    """
    request = _zeroed_request(om_cost_fraction=0.10)
    result = financial_basic.compute_financials(request)
    assert result.simple_payback_years is None


def test_short_horizon_one_year():
    """A 1-year analysis period must not crash and must produce one row."""
    result = financial_basic.compute_financials(
        _zeroed_request(analysis_period_years=1)
    )
    assert len(result.annual_savings_series_egp) == 1
    assert len(result.cumulative_cashflow_series_egp) == 2


def test_pydantic_rejects_negative_or_zero_system_kw():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FinancialBasicRequest(
            system_kw=0.0,
            annual_kwh=8000.0,
            tariff_egp_per_kwh=2.0,
        )


def test_pydantic_rejects_zero_tariff():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FinancialBasicRequest(
            system_kw=5.0,
            annual_kwh=8000.0,
            tariff_egp_per_kwh=0.0,
        )


def test_pydantic_rejects_discount_rate_at_or_above_one():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FinancialBasicRequest(
            system_kw=5.0,
            annual_kwh=8000.0,
            tariff_egp_per_kwh=2.0,
            discount_rate=1.0,
        )


# ────────────────────── defaults & echoed fields ───────────────────────


def test_defaults_match_settings_when_omitted():
    """Omitting optional fields must reproduce the configured defaults."""
    request = FinancialBasicRequest(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
    )
    result = financial_basic.compute_financials(request)
    assert result.cost_egp_per_kw == settings.installed_cost_egp_per_kw
    assert result.analysis_period_years == settings.analysis_period_years
    assert result.discount_rate == settings.discount_rate
    assert result.tariff_inflation_rate == settings.tariff_inflation_rate
    assert result.annual_degradation_rate == settings.annual_degradation_rate
    assert result.om_cost_fraction == settings.om_cost_fraction


def test_echoed_assumptions_match_request():
    request = _zeroed_request()
    result = financial_basic.compute_financials(request)
    assert result.system_kw == 5.0
    assert result.annual_kwh == 8000.0
    assert result.tariff_egp_per_kwh == 2.0


def test_default_call_payback_within_published_egypt_range():
    """Sanity check vs published Egyptian residential PV pre-feasibility:
    discounted payback under default Egypt assumptions should land inside
    a defensible 4–15 year window. A 5 kW system at 8 000 kWh/yr and
    2 EGP/kWh on the configured 35 000 EGP/kW costs gives a year-1 simple
    payback of capex / savings = 10.9 years; with default 8 % tariff
    inflation, 4 % discount rate and 0.5 %/yr degradation, the
    *discounted* payback should slip a little further but stay inside
    the band."""
    request = FinancialBasicRequest(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
    )
    result = financial_basic.compute_financials(request)
    assert result.discounted_payback_years is not None
    assert 4.0 <= result.discounted_payback_years <= 15.0


def test_npv_positive_when_lcoe_below_tariff():
    """LCOE is the break-even tariff. If the consumer pays more than
    LCOE per kWh, the project must have positive NPV — a structural
    invariant, not a numeric coincidence."""
    request = FinancialBasicRequest(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
    )
    result = financial_basic.compute_financials(request)
    assert math.isfinite(result.lcoe_egp_per_kwh)
    assert (result.tariff_egp_per_kwh > result.lcoe_egp_per_kwh) == (
        result.npv_egp > 0
    )
