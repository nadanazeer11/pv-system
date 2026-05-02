"""Tests for the OAT sensitivity / tornado kernel.

Most expectations are derived against closed-form simplifications
(zero discount, zero inflation, zero degradation, zero O&M) so the
NPV under a given parameter swing reduces to clean arithmetic. The
remaining tests pin down ranking, label discipline, and the payback
metric's null-handling.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.schemas.sensitivity import (
    SensitivityRange,
    SensitivityRequest,
)
from app.services import sensitivity


def _zeroed_request(**overrides) -> SensitivityRequest:
    """A baseline with every economic friction zeroed.

    Closed-form: NPV reduces to ``annual_kwh × tariff × years − capex``,
    so each parameter's NPV swing becomes pure arithmetic.
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
    return SensitivityRequest(**base)


# ─────────────────────────── ranking + structure ───────────────────


def test_returns_one_row_per_default_parameter():
    """The default sweep covers all seven supported parameters."""
    result = sensitivity.run_sensitivity(_zeroed_request())
    assert len(result.rows) == 7
    parameters = {row.parameter for row in result.rows}
    assert parameters == {
        "annual_kwh",
        "tariff_egp_per_kwh",
        "cost_egp_per_kw",
        "discount_rate",
        "tariff_inflation_rate",
        "annual_degradation_rate",
        "om_cost_fraction",
    }


def test_rows_are_sorted_by_swing_descending():
    """The dashboard tornado convention: largest swing on top."""
    result = sensitivity.run_sensitivity(_zeroed_request())
    swings = [row.swing for row in result.rows if row.swing is not None]
    assert swings == sorted(swings, reverse=True)


def test_rows_carry_human_readable_labels():
    """Every row must surface a plain-English, unit-bearing label."""
    result = sensitivity.run_sensitivity(_zeroed_request())
    labels = {row.parameter: row.label for row in result.rows}
    assert "kWh" in labels["annual_kwh"]
    assert "EGP/kWh" in labels["tariff_egp_per_kwh"]
    assert "EGP/kW" in labels["cost_egp_per_kw"]
    assert "%" in labels["discount_rate"]


def test_baseline_metric_matches_independent_kernel_call():
    """The baseline NPV the tornado reports must equal the deterministic kernel's NPV."""
    from app.schemas.financial import FinancialBasicRequest
    from app.services import financial_basic

    request = _zeroed_request()
    sensitivity_result = sensitivity.run_sensitivity(request)

    financial_payload = request.model_dump()
    # Drop the sensitivity-only fields the financial schema does not have.
    for key in ("metric", "ranges", "parameters"):
        financial_payload.pop(key, None)
    financial = financial_basic.compute_financials(FinancialBasicRequest(**financial_payload))
    assert sensitivity_result.metric_at_baseline == pytest.approx(financial.npv_egp)


# ───────────────── closed-form NPV swings (zeroed kernel) ──────────


def test_cost_swing_changes_npv_by_capacity_times_cost_delta():
    """In a zeroed kernel, swinging cost_egp_per_kw shifts NPV by ``-system_kw × Δcost``."""
    request = _zeroed_request()
    result = sensitivity.run_sensitivity(request)
    cost_row = next(r for r in result.rows if r.parameter == "cost_egp_per_kw")

    expected_swing = abs(
        request.system_kw * (cost_row.high_value - cost_row.low_value)
    )
    assert cost_row.swing == pytest.approx(expected_swing, rel=1e-9)
    # Higher cost ⇒ lower NPV.
    assert cost_row.metric_at_high < cost_row.metric_at_low


def test_tariff_swing_changes_npv_by_lifetime_kwh_times_tariff_delta():
    """In a zeroed kernel, swinging tariff shifts NPV by ``Δtariff × annual_kwh × years``."""
    request = _zeroed_request()
    result = sensitivity.run_sensitivity(request)
    tariff_row = next(r for r in result.rows if r.parameter == "tariff_egp_per_kwh")

    expected_swing = abs(
        (tariff_row.high_value - tariff_row.low_value)
        * request.annual_kwh
        * request.analysis_period_years
    )
    assert tariff_row.swing == pytest.approx(expected_swing, rel=1e-9)
    # Higher tariff ⇒ higher NPV.
    assert tariff_row.metric_at_high > tariff_row.metric_at_low


def test_yield_swing_changes_npv_by_lifetime_tariff_times_kwh_delta():
    """Closed-form yield swing in the zeroed kernel."""
    request = _zeroed_request()
    result = sensitivity.run_sensitivity(request)
    kwh_row = next(r for r in result.rows if r.parameter == "annual_kwh")

    expected_swing = abs(
        (kwh_row.high_value - kwh_row.low_value)
        * request.tariff_egp_per_kwh
        * request.analysis_period_years
    )
    assert kwh_row.swing == pytest.approx(expected_swing, rel=1e-9)
    assert kwh_row.metric_at_high > kwh_row.metric_at_low


def test_discount_rate_increase_lowers_npv():
    """Raising the discount rate must always lower NPV (positive cash flows)."""
    # Use the *full* default kernel (non-zero discount in baseline) so
    # the swing has both positive and negative directions to compare.
    request = SensitivityRequest(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0
    )
    result = sensitivity.run_sensitivity(request)
    row = next(r for r in result.rows if r.parameter == "discount_rate")
    assert row.metric_at_high < result.metric_at_baseline < row.metric_at_low


def test_inflation_increase_raises_npv():
    """Higher tariff inflation grows future savings ⇒ raises NPV."""
    request = SensitivityRequest(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0
    )
    result = sensitivity.run_sensitivity(request)
    row = next(r for r in result.rows if r.parameter == "tariff_inflation_rate")
    assert row.metric_at_high > row.metric_at_low


def test_degradation_increase_lowers_npv():
    """Higher degradation shrinks future generation ⇒ lowers NPV."""
    request = SensitivityRequest(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0
    )
    result = sensitivity.run_sensitivity(request)
    row = next(r for r in result.rows if r.parameter == "annual_degradation_rate")
    assert row.metric_at_high < row.metric_at_low


def test_om_increase_lowers_npv():
    """Higher O&M is a recurring cost ⇒ lowers NPV."""
    request = SensitivityRequest(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0
    )
    result = sensitivity.run_sensitivity(request)
    row = next(r for r in result.rows if r.parameter == "om_cost_fraction")
    assert row.metric_at_high < row.metric_at_low


# ────────────────────── deltas, sign, and consistency ──────────────


def test_delta_low_and_delta_high_match_metric_minus_baseline():
    """delta_low/high must equal ``metric_at_low/high − metric_at_baseline``."""
    result = sensitivity.run_sensitivity(_zeroed_request())
    for row in result.rows:
        assert row.delta_low == pytest.approx(row.metric_at_low - result.metric_at_baseline)
        assert row.delta_high == pytest.approx(
            row.metric_at_high - result.metric_at_baseline
        )


def test_baseline_value_matches_baseline_input():
    """Each row's baseline_value reflects the resolved deterministic baseline."""
    request = _zeroed_request()
    result = sensitivity.run_sensitivity(request)
    expected = {
        "annual_kwh": request.annual_kwh,
        "tariff_egp_per_kwh": request.tariff_egp_per_kwh,
        "cost_egp_per_kw": request.cost_egp_per_kw,
        "discount_rate": request.discount_rate,
        "tariff_inflation_rate": request.tariff_inflation_rate,
        "annual_degradation_rate": request.annual_degradation_rate,
        "om_cost_fraction": request.om_cost_fraction,
    }
    for row in result.rows:
        assert row.baseline_value == pytest.approx(expected[row.parameter])


# ───────────────────── ranges, parameter subset overrides ──────────


def test_range_overrides_used_when_supplied():
    """Caller-supplied ranges win over the configured defaults."""
    overrides = {"cost_egp_per_kw": SensitivityRange(low=20000.0, high=50000.0)}
    request = _zeroed_request()
    request_with_overrides = request.model_copy(update={"ranges": overrides})

    result = sensitivity.run_sensitivity(request_with_overrides)
    cost_row = next(r for r in result.rows if r.parameter == "cost_egp_per_kw")
    assert cost_row.low_value == 20000.0
    assert cost_row.high_value == 50000.0


def test_parameter_subset_restricts_returned_rows():
    """Asking for a subset must skip the other parameters."""
    request = _zeroed_request().model_copy(
        update={"parameters": ["annual_kwh", "tariff_egp_per_kwh"]}
    )
    result = sensitivity.run_sensitivity(request)
    assert len(result.rows) == 2
    assert {row.parameter for row in result.rows} == {
        "annual_kwh",
        "tariff_egp_per_kwh",
    }


def test_default_yield_range_is_relative_to_baseline_annual_kwh():
    """The default yield range scales with the baseline annual_kwh."""
    request = _zeroed_request(annual_kwh=10000.0)
    result = sensitivity.run_sensitivity(request)
    row = next(r for r in result.rows if r.parameter == "annual_kwh")
    lo, hi = settings.sensitivity_yield_factor_range
    assert row.low_value == pytest.approx(10000.0 * lo)
    assert row.high_value == pytest.approx(10000.0 * hi)


def test_default_tariff_range_is_relative_to_baseline_tariff():
    """The default tariff range scales with the baseline tariff."""
    request = _zeroed_request(tariff_egp_per_kwh=3.0)
    result = sensitivity.run_sensitivity(request)
    row = next(r for r in result.rows if r.parameter == "tariff_egp_per_kwh")
    lo, hi = settings.sensitivity_tariff_factor_range
    assert row.low_value == pytest.approx(3.0 * lo)
    assert row.high_value == pytest.approx(3.0 * hi)


def test_invalid_range_low_above_high_rejected():
    """The schema must reject low > high."""
    with pytest.raises(ValueError):
        SensitivityRange(low=50.0, high=10.0)


# ─────────────────────────── payback metric ────────────────────────


def test_payback_metric_returns_years_at_baseline():
    """The payback metric must return a year value at a healthy baseline."""
    request = SensitivityRequest(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
        metric="discounted_payback_years",
    )
    result = sensitivity.run_sensitivity(request)
    assert result.metric == "discounted_payback_years"
    assert result.metric_at_baseline is not None
    assert 1.0 < result.metric_at_baseline < 25.0


def test_payback_no_recovery_flagged_in_row():
    """When a swing forces payback past the horizon, the row flags it."""
    request = SensitivityRequest(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
        metric="discounted_payback_years",
        ranges={
            "tariff_egp_per_kwh": SensitivityRange(low=0.01, high=4.0),
        },
        parameters=["tariff_egp_per_kwh"],
    )
    result = sensitivity.run_sensitivity(request)
    row = result.rows[0]
    assert row.no_payback_at_low is True
    assert row.metric_at_low is None
    assert row.swing is None


def test_payback_no_recovery_rows_sort_to_bottom():
    """Rows whose swing is None (incomputable) must sort after computable rows."""
    request = SensitivityRequest(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
        metric="discounted_payback_years",
        ranges={
            "tariff_egp_per_kwh": SensitivityRange(low=0.01, high=4.0),
        },
    )
    result = sensitivity.run_sensitivity(request)
    swings = [row.swing for row in result.rows]
    # Once we hit a None, all subsequent rows are also None.
    none_seen = False
    for swing in swings:
        if swing is None:
            none_seen = True
        elif none_seen:
            pytest.fail("a finite swing came after a None — sort order is wrong")


# ───────────────────────── echoed assumptions ──────────────────────


def test_response_echoes_resolved_baseline_assumptions():
    """Defaults that fall through must appear in the echoed response."""
    request = SensitivityRequest(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0
    )
    result = sensitivity.run_sensitivity(request)
    assert result.cost_egp_per_kw == settings.installed_cost_egp_per_kw
    assert result.analysis_period_years == settings.analysis_period_years
    assert result.discount_rate == settings.discount_rate
    assert result.tariff_inflation_rate == settings.tariff_inflation_rate
    assert result.annual_degradation_rate == settings.annual_degradation_rate
    assert result.om_cost_fraction == settings.om_cost_fraction


def test_response_echoes_overrides_when_supplied():
    """Explicit overrides must appear in the echoed response."""
    request = _zeroed_request(cost_egp_per_kw=40000.0, discount_rate=0.05)
    result = sensitivity.run_sensitivity(request)
    assert result.cost_egp_per_kw == 40000.0
    assert result.discount_rate == 0.05
