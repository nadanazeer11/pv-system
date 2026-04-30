"""Tests for the EgyptERA tiered tariff service.

The kernel has three layers — single-month billing, twelve-month
aggregation + PV netting, and the size optimizer. Each layer is checked
both for closed-form arithmetic identities and for the structural
properties (monotonicity, non-negativity, conservation) the downstream
financial chain relies on.
"""
from __future__ import annotations

import math

import pytest

from app.config import settings
from app.schemas.tariff import (
    TariffBillRequest,
    TariffOptimizeRequest,
    TariffSavingsRequest,
    TariffTier,
)
from app.services import tiered_tariff
from app.services.tiered_tariff import _bill_one_month, _resolve_tiers


# ─────────────────────────── helper builders ──────────────────────────


def _flat_consumption(monthly_kwh: float) -> list[float]:
    return [monthly_kwh] * 12


def _tier(upper: float, price: float) -> TariffTier:
    return TariffTier(upper_kwh_per_month=upper, egp_per_kwh=price)


def _two_tier_schedule() -> list[TariffTier]:
    """Two-band schedule: 0–100 kWh @ 1.0 EGP, then >100 kWh @ 2.0 EGP."""
    return [_tier(100.0, 1.0), _tier(1e9, 2.0)]


# ─────────────────────────── month-level billing ──────────────────────


def test_zero_consumption_zero_bill_marginal_is_first_tier():
    bill = _bill_one_month(0.0, _two_tier_schedule())
    assert bill.bill_egp == pytest.approx(0.0)
    assert bill.consumption_kwh == pytest.approx(0.0)
    assert bill.marginal_tariff_egp_per_kwh == pytest.approx(1.0)
    assert sum(bill.per_tier_kwh) == pytest.approx(0.0)


def test_consumption_inside_first_tier_only_charges_first_rate():
    bill = _bill_one_month(40.0, _two_tier_schedule())
    assert bill.bill_egp == pytest.approx(40.0 * 1.0)
    assert bill.per_tier_kwh[0] == pytest.approx(40.0)
    assert bill.per_tier_kwh[1] == pytest.approx(0.0)
    assert bill.marginal_tariff_egp_per_kwh == pytest.approx(1.0)


def test_consumption_at_band_edge_uses_lower_band_only():
    """100 kWh exactly fills the first band; the second must be untouched."""
    bill = _bill_one_month(100.0, _two_tier_schedule())
    assert bill.bill_egp == pytest.approx(100.0 * 1.0)
    assert bill.per_tier_kwh[0] == pytest.approx(100.0)
    assert bill.per_tier_kwh[1] == pytest.approx(0.0)


def test_consumption_spans_two_bands_charges_each_at_its_rate():
    bill = _bill_one_month(150.0, _two_tier_schedule())
    expected = 100.0 * 1.0 + 50.0 * 2.0
    assert bill.bill_egp == pytest.approx(expected)
    assert bill.per_tier_kwh[0] == pytest.approx(100.0)
    assert bill.per_tier_kwh[1] == pytest.approx(50.0)
    assert bill.marginal_tariff_egp_per_kwh == pytest.approx(2.0)


def test_per_tier_kwh_sums_to_total_consumption():
    bill = _bill_one_month(187.5, _two_tier_schedule())
    assert sum(bill.per_tier_kwh) == pytest.approx(187.5)
    assert sum(bill.per_tier_egp) == pytest.approx(bill.bill_egp)


def test_marginal_rate_under_egyptera_default_top_tier():
    """1 200 kWh/month should land in the >1000 band → 1.55 EGP/kWh marginal."""
    tiers = _resolve_tiers(None)
    bill = _bill_one_month(1200.0, tiers)
    assert bill.marginal_tariff_egp_per_kwh == pytest.approx(1.55)


def test_egyptera_known_breakpoint_300_kwh():
    """A 300 kWh month under EgyptERA: hand-computed reference.

    50 × 0.58 + 50 × 0.68 + 100 × 0.83 + 100 × 1.25 = 29 + 34 + 83 + 125
    = 271 EGP. The marginal rate is the 4th band: 1.25.
    """
    tiers = _resolve_tiers(None)
    bill = _bill_one_month(300.0, tiers)
    assert bill.bill_egp == pytest.approx(271.0)
    assert bill.marginal_tariff_egp_per_kwh == pytest.approx(1.25)


# ───────────────────────────── annual bill ────────────────────────────


def test_compute_bill_aggregates_twelve_months():
    request = TariffBillRequest(
        monthly_consumption_kwh=_flat_consumption(50.0),
        tiers=_two_tier_schedule(),
    )
    result = tiered_tariff.compute_bill(request)
    assert result.annual_consumption_kwh == pytest.approx(12 * 50.0)
    assert result.annual_bill_egp == pytest.approx(12 * 50.0 * 1.0)


def test_average_tariff_lies_between_lowest_and_highest_used_band():
    request = TariffBillRequest(
        monthly_consumption_kwh=_flat_consumption(150.0),
        tiers=_two_tier_schedule(),
    )
    result = tiered_tariff.compute_bill(request)
    avg = result.average_tariff_egp_per_kwh
    assert 1.0 < avg < 2.0


def test_default_tiers_used_when_override_omitted():
    request = TariffBillRequest(
        monthly_consumption_kwh=_flat_consumption(200.0),
    )
    result = tiered_tariff.compute_bill(request)
    # Expected EgyptERA bill at 200 kWh: 50·0.58 + 50·0.68 + 100·0.83 = 146.
    assert result.monthly_breakdown[0].bill_egp == pytest.approx(146.0)
    assert len(result.tiers) == len(settings.egypt_residential_tariff_tiers)


def test_pydantic_rejects_eleven_month_profile():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TariffBillRequest(monthly_consumption_kwh=[100.0] * 11)


def test_pydantic_rejects_negative_consumption():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TariffBillRequest(monthly_consumption_kwh=[100.0] * 11 + [-1.0])


def test_pydantic_rejects_non_monotonic_tiers():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TariffBillRequest(
            monthly_consumption_kwh=_flat_consumption(50.0),
            tiers=[_tier(100.0, 1.0), _tier(50.0, 2.0)],
        )


# ─────────────────────────── PV savings ───────────────────────────────


def test_zero_generation_savings_is_zero():
    request = TariffSavingsRequest(
        monthly_consumption_kwh=_flat_consumption(150.0),
        monthly_generation_kwh=_flat_consumption(0.0),
        tiers=_two_tier_schedule(),
    )
    result = tiered_tariff.compute_savings(request)
    assert result.annual_savings_egp == pytest.approx(0.0)
    assert result.bill_after_egp == pytest.approx(result.bill_before_egp)


def test_savings_displaces_top_tier_first():
    """Saving 50 kWh at 150 kWh consumption must cut the top tier first.

    Under the two-tier schedule, consumption 150 → 100 means the
    bill drops from (100·1 + 50·2) = 200 to (100·1) = 100 — savings of
    100 EGP. The 50 displaced kWh therefore "earn" 2.0 EGP/kWh, not the
    average 1.333.
    """
    request = TariffSavingsRequest(
        monthly_consumption_kwh=_flat_consumption(150.0),
        monthly_generation_kwh=_flat_consumption(50.0),
        tiers=_two_tier_schedule(),
    )
    result = tiered_tariff.compute_savings(request)
    monthly_savings = result.annual_savings_egp / 12.0
    assert monthly_savings == pytest.approx(100.0)
    assert result.average_savings_egp_per_kwh == pytest.approx(2.0)


def test_average_savings_per_kwh_strictly_above_average_tariff_for_high_consumer():
    """Contribution B's headline claim, in test form.

    A high-consumer household saves *more* per kWh than its average
    tariff, because each saved kWh is taken off the top of the bill.
    """
    consumption = _flat_consumption(150.0)
    generation = _flat_consumption(40.0)
    bill = tiered_tariff.compute_bill(
        TariffBillRequest(
            monthly_consumption_kwh=consumption,
            tiers=_two_tier_schedule(),
        )
    )
    savings = tiered_tariff.compute_savings(
        TariffSavingsRequest(
            monthly_consumption_kwh=consumption,
            monthly_generation_kwh=generation,
            tiers=_two_tier_schedule(),
        )
    )
    assert (
        savings.average_savings_egp_per_kwh
        > bill.average_tariff_egp_per_kwh
    )


def test_excess_generation_counts_as_export_and_zero_credit_by_default():
    """Generation above monthly consumption falls into the export pool."""
    request = TariffSavingsRequest(
        monthly_consumption_kwh=_flat_consumption(50.0),
        monthly_generation_kwh=_flat_consumption(80.0),
        tiers=_two_tier_schedule(),
    )
    result = tiered_tariff.compute_savings(request)
    assert result.exported_kwh == pytest.approx(12 * 30.0)
    assert result.export_credit_egp == pytest.approx(0.0)
    assert result.bill_after_egp == pytest.approx(0.0)


def test_export_credit_increases_savings():
    consumption = _flat_consumption(50.0)
    generation = _flat_consumption(80.0)
    no_credit = tiered_tariff.compute_savings(
        TariffSavingsRequest(
            monthly_consumption_kwh=consumption,
            monthly_generation_kwh=generation,
            tiers=_two_tier_schedule(),
        )
    )
    with_credit = tiered_tariff.compute_savings(
        TariffSavingsRequest(
            monthly_consumption_kwh=consumption,
            monthly_generation_kwh=generation,
            tiers=_two_tier_schedule(),
            export_credit_egp_per_kwh=0.5,
        )
    )
    assert with_credit.annual_savings_egp > no_credit.annual_savings_egp
    expected_extra = 12 * 30.0 * 0.5
    assert with_credit.annual_savings_egp - no_credit.annual_savings_egp == pytest.approx(
        expected_extra
    )


def test_self_consumed_plus_exported_equals_total_generation():
    request = TariffSavingsRequest(
        monthly_consumption_kwh=[50.0, 100.0, 200.0] * 4,
        monthly_generation_kwh=[80.0, 80.0, 80.0] * 4,
        tiers=_two_tier_schedule(),
    )
    result = tiered_tariff.compute_savings(request)
    total_generation = sum([80.0, 80.0, 80.0] * 4)
    assert result.self_consumed_kwh + result.exported_kwh == pytest.approx(
        total_generation
    )


def test_low_consumer_savings_below_high_consumer_savings_per_kwh():
    """Same generation, different consumption → different per-kWh value."""
    generation = _flat_consumption(40.0)
    high = tiered_tariff.compute_savings(
        TariffSavingsRequest(
            monthly_consumption_kwh=_flat_consumption(150.0),
            monthly_generation_kwh=generation,
            tiers=_two_tier_schedule(),
        )
    )
    low = tiered_tariff.compute_savings(
        TariffSavingsRequest(
            monthly_consumption_kwh=_flat_consumption(60.0),
            monthly_generation_kwh=generation,
            tiers=_two_tier_schedule(),
        )
    )
    assert (
        high.average_savings_egp_per_kwh > low.average_savings_egp_per_kwh
    )


# ──────────────────────────── optimizer ───────────────────────────────


def _baseline_generation_for_5kw() -> list[float]:
    """Synthetic monthly profile: ~8 000 kWh/yr for a 5 kW system.

    Higher generation in summer than winter mimics a Cairo profile
    qualitatively without depending on a TMY file.
    """
    pattern = [
        500.0,
        550.0,
        650.0,
        700.0,
        780.0,
        820.0,
        850.0,
        820.0,
        750.0,
        680.0,
        550.0,
        500.0,
    ]
    total = sum(pattern)
    target = 8000.0
    return [v * (target / total) for v in pattern]


def test_optimizer_returns_zero_when_capex_too_high():
    """If installed cost is huge no candidate is profitable; the zero-kW
    candidate (NPV=0) must be the optimum."""
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(150.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=10.0,
        grid_step_kw=1.0,
        cost_egp_per_kw=1_000_000_000.0,
        tiers=_two_tier_schedule(),
    )
    result = tiered_tariff.optimize_system_size(request)
    assert result.optimal_system_kw == pytest.approx(0.0)
    assert result.optimal_npv_egp == pytest.approx(0.0)


def test_optimizer_picks_a_positive_size_for_realistic_egypt_inputs():
    """Under default Egypt assumptions a high-consumption household
    should benefit from *some* PV. A zero recommendation would indicate
    a regression in the kernel."""
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(600.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=10.0,
        grid_step_kw=0.5,
    )
    result = tiered_tariff.optimize_system_size(request)
    assert result.optimal_system_kw > 0.0
    assert result.optimal_npv_egp > 0.0


def test_optimizer_candidate_grid_includes_max_kw():
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(300.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=7.3,
        grid_step_kw=1.0,
    )
    result = tiered_tariff.optimize_system_size(request)
    sizes = [c.system_kw for c in result.candidates]
    # 0,1,2,3,4,5,6,7,7.3 — must include both the regular grid and the max.
    assert sizes[0] == pytest.approx(0.0)
    assert sizes[-1] == pytest.approx(7.3)


def test_optimizer_capex_scales_linearly_with_kw():
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(300.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=10.0,
        grid_step_kw=1.0,
        cost_egp_per_kw=10000.0,
    )
    result = tiered_tariff.optimize_system_size(request)
    for candidate in result.candidates:
        assert candidate.capex_egp == pytest.approx(candidate.system_kw * 10000.0)


def test_optimizer_generation_scales_linearly_with_kw():
    baseline = _baseline_generation_for_5kw()
    annual_baseline = sum(baseline)
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(300.0),
        baseline_monthly_generation_kwh=baseline,
        baseline_system_kw=5.0,
        max_system_kw=10.0,
        grid_step_kw=1.0,
    )
    result = tiered_tariff.optimize_system_size(request)
    for candidate in result.candidates:
        expected_gen = annual_baseline * (candidate.system_kw / 5.0)
        assert candidate.annual_generation_kwh == pytest.approx(expected_gen, rel=1e-6)


def test_optimizer_flat_tariff_optimum_at_least_as_large_as_tier_aware():
    """Contribution B's structural claim.

    The flat-tariff model overvalues savings in the cheap tiers, so it
    recommends an equal-or-larger system than the tier-aware optimum.
    Strict inequality is *not* guaranteed (for a household whose
    consumption never reaches the cheap tiers, the two coincide), so
    we assert ≥ rather than >.
    """
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(600.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=15.0,
        grid_step_kw=0.5,
    )
    result = tiered_tariff.optimize_system_size(request)
    assert result.flat_tariff_optimum_kw >= result.optimal_system_kw - 1e-9


def test_optimizer_export_credit_increases_or_holds_optimal_size():
    """Adding a positive export credit can only raise the value of
    extra generation, so the recommended size must not shrink."""
    no_export = tiered_tariff.optimize_system_size(
        TariffOptimizeRequest(
            monthly_consumption_kwh=_flat_consumption(600.0),
            baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
            baseline_system_kw=5.0,
            max_system_kw=15.0,
            grid_step_kw=0.5,
        )
    )
    with_export = tiered_tariff.optimize_system_size(
        TariffOptimizeRequest(
            monthly_consumption_kwh=_flat_consumption(600.0),
            baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
            baseline_system_kw=5.0,
            max_system_kw=15.0,
            grid_step_kw=0.5,
            export_credit_egp_per_kwh=1.0,
        )
    )
    assert with_export.optimal_system_kw >= no_export.optimal_system_kw - 1e-9


def test_optimizer_npv_curve_concave_at_optimum():
    """NPV must rise up to the optimum and then non-strictly fall.

    Walks the candidate grid and verifies it is unimodal — tier-aware
    NPV is piecewise-linear concave between band boundaries (each kWh
    above the optimum is valued at the *next* lower tier rate), so
    the grid sweep should never see a second peak.
    """
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(600.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=20.0,
        grid_step_kw=0.5,
    )
    result = tiered_tariff.optimize_system_size(request)
    npvs = [c.npv_egp for c in result.candidates]
    optimum_idx = npvs.index(max(npvs))
    # Non-decreasing up to the optimum.
    for i in range(1, optimum_idx + 1):
        assert npvs[i] >= npvs[i - 1] - 1e-6
    # Non-increasing past the optimum.
    for i in range(optimum_idx + 1, len(npvs)):
        assert npvs[i] <= npvs[i - 1] + 1e-6


def test_optimizer_pydantic_rejects_zero_baseline_kw():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TariffOptimizeRequest(
            monthly_consumption_kwh=_flat_consumption(150.0),
            baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
            baseline_system_kw=0.0,
            max_system_kw=10.0,
        )


def test_optimizer_echoed_assumptions_fall_back_to_settings():
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(300.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=10.0,
        grid_step_kw=1.0,
    )
    result = tiered_tariff.optimize_system_size(request)
    assert result.discount_rate == settings.discount_rate
    assert result.tariff_inflation_rate == settings.tariff_inflation_rate
    assert result.annual_degradation_rate == settings.annual_degradation_rate
    assert result.om_cost_fraction == settings.om_cost_fraction
    assert result.cost_egp_per_kw == settings.installed_cost_egp_per_kw
    assert result.analysis_period_years == settings.analysis_period_years


# ─────────────────────────── error paths ──────────────────────────────


def test_consumption_above_finite_top_band_raises():
    """If the top band is *not* unbounded and consumption overflows it,
    the kernel must raise a clear error rather than silently dropping
    the excess kWh."""
    bounded_schedule = [_tier(100.0, 1.0), _tier(200.0, 2.0)]  # caps at 200 kWh
    with pytest.raises(tiered_tariff.TariffError):
        _bill_one_month(250.0, bounded_schedule)


def test_resolve_tiers_returns_egyptera_default():
    tiers = _resolve_tiers(None)
    assert len(tiers) == len(settings.egypt_residential_tariff_tiers)
    assert tiers[0].egp_per_kwh == pytest.approx(0.58)
    assert tiers[-1].egp_per_kwh == pytest.approx(1.55)


def test_optimizer_with_zero_consumption_picks_zero_size_when_no_export_credit():
    """With no consumption and no export credit, generation has zero
    value → no positive-NPV candidate → optimum is 0 kW."""
    request = TariffOptimizeRequest(
        monthly_consumption_kwh=_flat_consumption(0.0),
        baseline_monthly_generation_kwh=_baseline_generation_for_5kw(),
        baseline_system_kw=5.0,
        max_system_kw=10.0,
        grid_step_kw=1.0,
    )
    result = tiered_tariff.optimize_system_size(request)
    assert result.optimal_system_kw == pytest.approx(0.0)


def test_savings_is_finite_under_default_egyptera_schedule():
    """Smoke test on the live default schedule end-to-end."""
    request = TariffSavingsRequest(
        monthly_consumption_kwh=_flat_consumption(500.0),
        monthly_generation_kwh=_flat_consumption(300.0),
    )
    result = tiered_tariff.compute_savings(request)
    assert math.isfinite(result.annual_savings_egp)
    assert result.annual_savings_egp > 0.0
