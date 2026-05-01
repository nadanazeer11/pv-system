"""Tests for the Monte Carlo uncertainty service.

The hardest part of testing a stochastic kernel is that "almost every"
assertion needs a tolerance. The strategy adopted here is to drive most
expectations from a *deterministic collapse*: when every distribution
has zero spread (σ = 0 normal, low = mode = high triangular) the engine
must behave identically to the deterministic ``financial_basic`` model,
so closed-form answers re-enter the picture. Stochastic-only properties
(monotonic spread, percentile ordering, reproducibility under seed) are
asserted with structural inequalities rather than fragile numeric
tolerances.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from app.config import settings
from app.schemas.financial import FinancialBasicRequest
from app.schemas.monte_carlo import Distribution, MonteCarloRequest
from app.services import financial_basic
from app.services import monte_carlo as mc


# ─────────────────────────── Fixtures ───────────────────────────────


def _zero_dist_request(**overrides) -> MonteCarloRequest:
    """Request with every distribution collapsed to zero variance.

    Under this configuration each Monte Carlo "draw" produces the same
    cash-flow series, so percentile bands shrink to a single point and
    the result must equal the deterministic financial_basic model
    augmented with one inverter replacement event at the configured
    mode year.
    """
    base = {
        "system_kw": 5.0,
        "annual_kwh": 8000.0,
        "tariff_egp_per_kwh": 2.0,
        "analysis_period_years": 25,
        "discount_rate": 0.04,
        "n_simulations": 200,
        "random_seed": 7,
        "degradation_rate_dist": Distribution(
            kind="triangular", low=0.005, mode=0.005, high=0.005
        ),
        "tariff_inflation_rate_dist": Distribution(
            kind="normal", mean=0.08, std=0.0
        ),
        "om_cost_fraction_dist": Distribution(
            kind="triangular", low=0.01, mode=0.01, high=0.01
        ),
        "cost_egp_per_kw_dist": Distribution(
            kind="triangular", low=35000.0, mode=35000.0, high=35000.0
        ),
        "annual_yield_factor_dist": Distribution(
            kind="normal", mean=1.0, std=0.0
        ),
        "inverter_replacement_year_dist": Distribution(
            kind="triangular", low=12.0, mode=12.0, high=12.0
        ),
        "inverter_replacement_cost_fraction_dist": Distribution(
            kind="triangular", low=0.10, mode=0.10, high=0.10
        ),
    }
    base.update(overrides)
    return MonteCarloRequest(**base)


# ────────────────────────── Distribution validation ─────────────────


def test_normal_distribution_requires_mean_and_std():
    with pytest.raises(ValueError, match="mean"):
        Distribution(kind="normal", mean=0.05)


def test_triangular_distribution_requires_all_three_bounds():
    with pytest.raises(ValueError, match="low"):
        Distribution(kind="triangular", low=0.0, high=1.0)


def test_triangular_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="low <= mode <= high"):
        Distribution(kind="triangular", low=1.0, mode=2.0, high=0.5)


def test_triangular_zero_width_is_permitted_as_constant():
    """A zero-width triangular collapses to a deterministic constant —
    a convenience for callers who want to disable one source of
    uncertainty without restructuring their request."""
    dist = Distribution(kind="triangular", low=1.0, mode=1.0, high=1.0)
    assert dist.low == dist.mode == dist.high == 1.0


def test_clip_min_must_not_exceed_clip_max():
    with pytest.raises(ValueError, match="clip_min"):
        Distribution(kind="normal", mean=0.0, std=1.0, clip_min=1.0, clip_max=0.0)


# ─────────────────── Sampling primitive (white-box) ─────────────────


def test_sample_normal_zero_std_returns_constant_array():
    rng = np.random.default_rng(0)
    dist = Distribution(kind="normal", mean=0.05, std=0.0)
    samples = mc._sample(dist, rng, 100)
    assert samples.shape == (100,)
    assert np.all(samples == 0.05)


def test_sample_triangular_zero_width_returns_constant_array():
    """A schema-permitted zero-width triangular must sample to a
    deterministic constant: ``np.random.Generator.triangular`` would
    raise on equal bounds, so the kernel guard is what callers depend
    on for the "collapse to constant" idiom."""
    rng = np.random.default_rng(0)
    dist = Distribution(kind="triangular", low=2.0, mode=2.0, high=2.0)
    samples = mc._sample(dist, rng, 50)
    assert np.all(samples == 2.0)


def test_sample_normal_clipping_applied():
    rng = np.random.default_rng(1)
    dist = Distribution(
        kind="normal", mean=0.0, std=1.0, clip_min=-0.5, clip_max=0.5
    )
    samples = mc._sample(dist, rng, 5000)
    assert samples.min() >= -0.5
    assert samples.max() <= 0.5


def test_sample_triangular_within_bounds():
    rng = np.random.default_rng(2)
    dist = Distribution(kind="triangular", low=10.0, mode=12.0, high=15.0)
    samples = mc._sample(dist, rng, 5000)
    assert samples.min() >= 10.0
    assert samples.max() <= 15.0


def test_sample_triangular_mean_close_to_published_formula():
    """The mean of a triangular(a, c, b) is (a + c + b) / 3."""
    rng = np.random.default_rng(3)
    dist = Distribution(kind="triangular", low=0.002, mode=0.005, high=0.010)
    samples = mc._sample(dist, rng, 50_000)
    expected = (0.002 + 0.005 + 0.010) / 3.0
    assert math.isclose(samples.mean(), expected, abs_tol=1e-4)


# ────────────────── Reproducibility under random_seed ───────────────


def test_same_seed_returns_identical_result():
    """Byte-identical re-run is the contract for the test suite and
    for any thesis figure a reviewer wants to reproduce.
    """
    req_kwargs = dict(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
        n_simulations=200,
        random_seed=123,
    )
    a = mc.run_monte_carlo(MonteCarloRequest(**req_kwargs))
    b = mc.run_monte_carlo(MonteCarloRequest(**req_kwargs))
    assert a.payback_years.p50 == b.payback_years.p50
    assert a.npv_egp.p50 == b.npv_egp.p50
    assert a.lcoe_egp_per_kwh.p50 == b.lcoe_egp_per_kwh.p50
    assert a.payback_probability == b.payback_probability


def test_different_seeds_produce_different_results():
    base = dict(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
        n_simulations=300,
    )
    a = mc.run_monte_carlo(MonteCarloRequest(**base, random_seed=1))
    b = mc.run_monte_carlo(MonteCarloRequest(**base, random_seed=2))
    assert a.npv_egp.p50 != b.npv_egp.p50


def test_no_seed_still_runs_and_is_well_formed():
    """When the caller omits ``random_seed`` the engine must still
    return a fully-populated, schema-valid response."""
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=100,
        )
    )
    assert result.n_simulations == 100
    assert 0.0 <= result.payback_probability <= 1.0


# ──────────────── Deterministic-collapse equivalence ────────────────


def test_zero_variance_collapses_to_single_point():
    """With every σ = 0 the percentile band reduces to a point: max == min."""
    result = mc.run_monte_carlo(_zero_dist_request())
    assert result.payback_years.minimum == pytest.approx(
        result.payback_years.maximum, rel=1e-9
    )
    assert result.npv_egp.minimum == pytest.approx(
        result.npv_egp.maximum, rel=1e-9
    )
    assert result.payback_years.std == pytest.approx(0.0, abs=1e-9)


def test_zero_variance_npv_matches_financial_basic_minus_inverter_cost():
    """At σ = 0 the kernel must equal the deterministic financial_basic
    NPV minus the present-value of one inverter replacement at year 12.

    capex × 0.10 / (1 + r)^12 is the additional discounted cost the
    Monte Carlo engine takes on board; financial_basic does not (yet)
    model inverter replacement.
    """
    request = _zero_dist_request()
    result = mc.run_monte_carlo(request)

    deterministic = financial_basic.compute_financials(
        FinancialBasicRequest(
            system_kw=request.system_kw,
            annual_kwh=request.annual_kwh,
            tariff_egp_per_kwh=request.tariff_egp_per_kwh,
            cost_egp_per_kw=35000.0,
            analysis_period_years=request.analysis_period_years,
            discount_rate=request.discount_rate,
            tariff_inflation_rate=0.08,
            annual_degradation_rate=0.005,
            om_cost_fraction=0.01,
        )
    )
    capex = request.system_kw * 35000.0
    inverter_pv = capex * 0.10 / (1.0 + request.discount_rate) ** 12
    expected_npv = deterministic.npv_egp - inverter_pv
    assert result.npv_egp.p50 == pytest.approx(expected_npv, rel=1e-6)


def test_zero_variance_lifetime_savings_matches_financial_basic():
    """Lifetime nominal savings is independent of discount rate and
    inverter cost, so the equality with financial_basic is exact.
    """
    request = _zero_dist_request()
    result = mc.run_monte_carlo(request)
    deterministic = financial_basic.compute_financials(
        FinancialBasicRequest(
            system_kw=request.system_kw,
            annual_kwh=request.annual_kwh,
            tariff_egp_per_kwh=request.tariff_egp_per_kwh,
            cost_egp_per_kw=35000.0,
            analysis_period_years=request.analysis_period_years,
            discount_rate=request.discount_rate,
            tariff_inflation_rate=0.08,
            annual_degradation_rate=0.005,
            om_cost_fraction=0.01,
        )
    )
    assert result.lifetime_savings_egp.p50 == pytest.approx(
        deterministic.lifetime_savings_egp, rel=1e-6
    )


# ───────────────────── Structural invariants ────────────────────────


def test_percentiles_are_strictly_ordered():
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=500, random_seed=42,
        )
    )
    p = result.npv_egp
    assert p.p05 <= p.p10 <= p.p25 <= p.p50 <= p.p75 <= p.p90 <= p.p95
    assert p.minimum <= p.p05
    assert p.maximum >= p.p95


def test_higher_variance_gives_wider_band():
    """Increasing tariff inflation σ must strictly widen the NPV band.

    Sanity check that the engine is actually propagating the
    distribution we hand it, not silently replacing it with a default.
    """
    base = dict(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
        n_simulations=1000, random_seed=99,
    )
    narrow = mc.run_monte_carlo(
        MonteCarloRequest(
            **base,
            tariff_inflation_rate_dist=Distribution(
                kind="normal", mean=0.08, std=0.005
            ),
        )
    )
    wide = mc.run_monte_carlo(
        MonteCarloRequest(
            **base,
            tariff_inflation_rate_dist=Distribution(
                kind="normal", mean=0.08, std=0.05
            ),
        )
    )
    assert wide.npv_egp.std > narrow.npv_egp.std


def test_simulation_count_respected():
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=250, random_seed=4,
        )
    )
    assert result.n_simulations == 250


def test_histogram_count_sums_to_paid_back_simulations():
    """The payback histogram is built only over simulations that
    recovered capex within the horizon. Its total count must equal
    payback_probability × n_simulations.
    """
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=400, random_seed=12,
        )
    )
    expected = round(result.payback_probability * result.n_simulations)
    assert sum(result.payback_histogram.counts) == expected


def test_npv_histogram_count_equals_total_simulations():
    """All simulations contribute to the NPV histogram (NPV is finite by
    construction for any well-defined draw)."""
    n = 600
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=n, random_seed=33,
        )
    )
    assert sum(result.npv_histogram.counts) == n


def test_histogram_bin_edges_monotonic():
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=200, random_seed=5,
        )
    )
    for hist in (result.payback_histogram, result.npv_histogram):
        edges = hist.bin_edges
        assert all(b > a for a, b in zip(edges, edges[1:]))


# ────────────────────── Egypt sanity range ──────────────────────────


def test_default_egypt_residential_payback_in_published_range():
    """A 5 kW system at 1 600 kWh/kW/yr and 2.0 EGP/kWh average tariff
    should pay back in 7–14 years under the configured Egypt-tuned
    distribution defaults (Esmail & Negm 2021, Egyptian residential
    rooftop pre-feasibility studies). The wide window absorbs Monte
    Carlo sampling noise at 1 000 draws.
    """
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=1000, random_seed=2026,
        )
    )
    assert 7.0 <= result.payback_years.p50 <= 14.0
    assert result.payback_probability >= 0.95
    assert result.positive_npv_probability >= 0.90


def test_extreme_capex_sinks_payback_probability():
    """Loading installed cost an order of magnitude above the Egypt
    market must drive the probability of positive NPV well below the
    baseline — sanity check that the kernel propagates the cost
    distribution as a cost, not as a free parameter."""
    base = dict(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
        n_simulations=500, random_seed=2027,
    )
    cheap = mc.run_monte_carlo(MonteCarloRequest(**base))
    expensive = mc.run_monte_carlo(
        MonteCarloRequest(
            **base,
            cost_egp_per_kw_dist=Distribution(
                kind="triangular", low=290000.0, mode=300000.0, high=310000.0
            ),
        )
    )
    assert expensive.positive_npv_probability < cheap.positive_npv_probability
    assert expensive.positive_npv_probability < 0.10


def test_positive_npv_probability_bounded_to_unit_interval():
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=200, random_seed=7,
        )
    )
    assert 0.0 <= result.positive_npv_probability <= 1.0
    assert 0.0 <= result.payback_probability <= 1.0


def test_short_horizon_can_produce_unrecovered_simulations():
    """A 3-year analysis horizon is far too short for a residential PV
    system to break even, so the payback probability must be small and
    the percentile band can legitimately collapse to an empty set."""
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            analysis_period_years=3, n_simulations=200, random_seed=11,
        )
    )
    assert result.payback_probability <= 0.1


# ───────────────────── Override resolution ──────────────────────────


def test_explicit_distribution_overrides_default():
    """Passing a custom degradation distribution must change the
    output relative to the default. White-box knob test."""
    base = dict(
        system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
        n_simulations=400, random_seed=8,
    )
    default = mc.run_monte_carlo(MonteCarloRequest(**base))
    aggressive_deg = mc.run_monte_carlo(
        MonteCarloRequest(
            **base,
            degradation_rate_dist=Distribution(
                kind="triangular", low=0.04, mode=0.05, high=0.06
            ),
        )
    )
    # 5 % per-year degradation halves output by year ~14, drastically
    # cutting lifetime savings.
    assert aggressive_deg.lifetime_savings_egp.p50 < default.lifetime_savings_egp.p50


def test_request_falls_back_to_settings_for_horizon_and_discount():
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=100, random_seed=99,
        )
    )
    assert result.analysis_period_years == settings.analysis_period_years
    assert result.discount_rate == settings.discount_rate


def test_kernel_rejects_non_positive_horizon():
    """The Pydantic schema enforces ``ge=1``, so the kernel guard is
    only reached when the schema is bypassed (e.g. ``model_construct``).
    Defending the kernel itself keeps the service safe to import."""
    bypassed = MonteCarloRequest.model_construct(
        system_kw=5.0,
        annual_kwh=8000.0,
        tariff_egp_per_kwh=2.0,
        n_simulations=100,
        random_seed=1,
        analysis_period_years=0,
        discount_rate=None,
    )
    with pytest.raises(mc.MonteCarloError):
        mc.run_monte_carlo(bypassed)


def test_unknown_distribution_kind_raises_at_sample():
    """Direct kernel-level guard: a distribution constructed via
    ``model_construct`` (bypassing schema validation) with an unknown
    kind must fail loudly rather than silently sampling zeros."""
    rng = np.random.default_rng(0)
    bad = Distribution.model_construct(kind="cauchy", mean=0.0, std=1.0)
    with pytest.raises(mc.MonteCarloError):
        mc._sample(bad, rng, 10)


# ─────────────────── Day 16 — fan-chart trajectory ──────────────────


def test_trajectory_year_index_covers_capex_through_horizon():
    """The fan chart's x-axis is years 0..T inclusive: year 0 is the
    capex draw, year T is the end of the analysis horizon. Length
    must equal analysis_period_years + 1."""
    horizon = 25
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            analysis_period_years=horizon,
            n_simulations=200, random_seed=11,
        )
    )
    traj = result.cumulative_cash_flow_trajectory
    assert traj.year_index == list(range(horizon + 1))
    for band in (traj.p05, traj.p25, traj.p50, traj.p75, traj.p95, traj.mean):
        assert len(band) == horizon + 1


def test_trajectory_year_zero_is_negative_capex():
    """Year-0 cumulative cash flow is the (negative) capex draw before
    any savings have accrued. Every percentile band must therefore be
    strictly negative at index 0 — sanity check that the algebra
    inside the cumulative matrix follows the deterministic chain."""
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=300, random_seed=44,
        )
    )
    traj = result.cumulative_cash_flow_trajectory
    for band in (traj.p05, traj.p25, traj.p50, traj.p75, traj.p95, traj.mean):
        assert band[0] < 0


def test_trajectory_percentile_bands_are_ordered():
    """At every year, p05 ≤ p25 ≤ p50 ≤ p75 ≤ p95. This is the most
    important structural property a fan chart relies on — if any
    crossing happened the visualisation would render absurd
    overlapping ribbons."""
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=400, random_seed=55,
        )
    )
    traj = result.cumulative_cash_flow_trajectory
    for k in range(len(traj.year_index)):
        assert traj.p05[k] <= traj.p25[k] <= traj.p50[k]
        assert traj.p50[k] <= traj.p75[k] <= traj.p95[k]


def test_trajectory_zero_variance_collapses_to_deterministic_chain():
    """When every distribution has zero spread the fan chart must
    collapse to a single curve (all bands identical), and that curve
    must match the deterministic financial_basic cumulative cash flow
    augmented with the inverter-replacement event."""
    request = _zero_dist_request(n_simulations=50)
    result = mc.run_monte_carlo(request)
    traj = result.cumulative_cash_flow_trajectory
    for k in range(len(traj.year_index)):
        # Every band collapses onto the same value.
        assert math.isclose(traj.p05[k], traj.p95[k], abs_tol=1e-6)
        assert math.isclose(traj.p50[k], traj.mean[k], abs_tol=1e-6)
    # The deterministic median must cross zero at the deterministic
    # payback year reported in the same response.
    payback_year = result.payback_years.p50
    assert traj.p50[int(math.ceil(payback_year))] >= 0
    assert traj.p50[int(math.floor(payback_year))] <= 0


def test_trajectory_median_endpoint_matches_npv_median():
    """End of horizon — median cumulative discounted cash flow must
    equal the median NPV by construction (same algebra: -capex plus
    sum of discounted net cash flows). Tolerance accounts for the
    fact that column-wise medians and row-wise NPV medians can pick
    different simulation paths under non-zero variance."""
    request = _zero_dist_request(n_simulations=50)
    result = mc.run_monte_carlo(request)
    traj = result.cumulative_cash_flow_trajectory
    # Under zero variance, every row of the cumulative matrix is
    # identical, so column-wise and row-wise medians coincide exactly.
    assert math.isclose(traj.p50[-1], result.npv_egp.p50, rel_tol=1e-6)


def test_trajectory_widens_under_non_zero_variance():
    """The interquartile spread at the end of the horizon must be
    materially larger than at year 0 — uncertainty propagates and
    accumulates over the analysis period."""
    result = mc.run_monte_carlo(
        MonteCarloRequest(
            system_kw=5.0, annual_kwh=8000.0, tariff_egp_per_kwh=2.0,
            n_simulations=600, random_seed=99,
        )
    )
    traj = result.cumulative_cash_flow_trajectory
    iqr_year_0 = traj.p75[0] - traj.p25[0]
    iqr_horizon = traj.p75[-1] - traj.p25[-1]
    assert iqr_horizon > iqr_year_0
    assert iqr_horizon > 1000.0  # EGP — defensible at default Egypt spreads
