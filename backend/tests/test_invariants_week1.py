"""Week-1 cross-service invariants.

Day 7's deliverable per ``PLAN.md`` is "Unit tests for energy + sizing +
financial". The per-service files already cover each kernel in isolation;
this module pins the *cross-service* properties that no individual file
can check on its own:

1. The dual-energy chains and the financial kernel both treat the system
   sizing produced by ``pv_sizing`` as their unit of capacity. A breaking
   schema change in any one of those three services would slip past the
   per-service suites. The end-to-end "100 m² roof → positive NPV"
   pipeline test catches it loudly.
2. Both energy chains expose a 12-entry ``monthly_kwh`` series and an
   8 760-entry ``ac_hourly`` series. Two structural identities must hold
   exactly — Σ monthly == annual, and ac_hourly ≥ 0 everywhere — so
   downstream consumers (Day-15 comparison view, Day-9 Monte Carlo) can
   trust those invariants without re-validating.
3. The simulation must be deterministic: re-running with the same TMY
   and parameters must produce bit-identical aggregates. Day 9's Monte
   Carlo engine relies on this — its only source of randomness is the
   parameter sampler, *not* the kernel. A non-deterministic kernel would
   silently widen the resulting confidence intervals.
4. The financial kernel treats both ``annual_kwh`` figures (pvlib and
   manual) identically. A defensible thesis must show that the **payback
   ordering** is the same regardless of which energy chain feeds the
   financial model — otherwise the cross-validation chapter has nothing
   to compare.

These invariants are the contract between the week-1 services. Tagging
``v0.1-backend-core`` (PLAN.md Day 7) is the moment that contract is
frozen for Week-2 integration work.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib
import pytest

from app.schemas.financial import FinancialBasicRequest
from app.schemas.sizing import SizingRequest
from app.services import (
    energy_manual,
    energy_pvlib,
    financial_basic,
    pv_sizing,
)


# ───────────────────────── shared fixtures ─────────────────────────


def _cairo_clearsky_tmy() -> pd.DataFrame:
    """Cairo clear-sky TMY synthesised from pvlib's clear-sky engine.

    Identical recipe to the per-service files so any cross-service delta
    is attributable to the integration boundary, not to mismatched inputs.
    """
    lat, lon = 30.0444, 31.2357
    idx = pd.date_range("2020-01-01", periods=8760, freq="h", tz="UTC")
    loc = pvlib.location.Location(lat, lon, tz="UTC", altitude=23)
    cs = loc.get_clearsky(idx)
    doy = idx.dayofyear.to_numpy()
    hod = idx.hour.to_numpy()
    air_temp = (
        22.0
        + 8.0 * np.cos((doy - 200) * 2 * np.pi / 365.25)
        + 5.0 * np.cos((hod - 14) * np.pi / 12)
    )
    return pd.DataFrame(
        {
            "ghi": cs["ghi"],
            "dni": cs["dni"],
            "dhi": cs["dhi"],
            "temp_air": air_temp,
            "wind_speed": 3.0,
        },
        index=idx,
    )


# ─────────────── pipeline integration: sizing → energy → financial ───────────────


def test_full_pipeline_cairo_roof_to_positive_npv():
    """A canonical Cairo rooftop produces a positive-NPV system through
    every week-1 service in sequence.

    This is the *only* test that exercises the three week-1 kernels
    together. A schema rename, a unit error, or a sign flip in any one
    of them would surface here as either an assertion failure or an
    exception during chaining — even if every per-service file still
    passes. Tagging v0.1-backend-core depends on this passing.
    """
    sizing = pv_sizing.compute_system_size(SizingRequest(roof_area_m2=100.0))
    assert sizing.system_kw > 0

    tmy = _cairo_clearsky_tmy()
    sim = energy_pvlib.simulate(
        tmy, latitude=30.0444, longitude=31.2357, system_kw=sizing.system_kw
    )
    assert sim.annual_kwh > 0

    fin = financial_basic.compute_financials(
        FinancialBasicRequest(
            system_kw=sizing.system_kw,
            annual_kwh=sim.annual_kwh,
            tariff_egp_per_kwh=2.0,
        )
    )

    # A 17.1 kW Cairo system at 2 EGP/kWh on default Egypt assumptions
    # must clear NPV > 0 and pay back within the 25-year horizon. If
    # this drifts substantially, one of the three kernels has changed
    # behaviour.
    assert fin.npv_egp > 0
    assert fin.discounted_payback_years is not None
    assert 1.0 < fin.discounted_payback_years < 25.0
    # LCOE must lie strictly below the tariff — a structural consequence
    # of NPV > 0, sanity-checked across the whole pipeline.
    assert fin.lcoe_egp_per_kwh < fin.tariff_egp_per_kwh


def test_pvlib_and_manual_chains_agree_on_payback_ordering():
    """Feeding the financial kernel with either the pvlib or the manual
    annual_kwh must produce paybacks that *order the same way* against
    each other (i.e., neither chain alone determines whether the project
    pays back). This is the cross-validation guarantee that lets the
    thesis quote a single payback figure with a confidence band."""
    tmy = _cairo_clearsky_tmy()
    pv = energy_pvlib.simulate(tmy, latitude=30.0444, longitude=31.2357, system_kw=5.0)
    mn = energy_manual.simulate(tmy, latitude=30.0444, longitude=31.2357, system_kw=5.0)

    fin_pv = financial_basic.compute_financials(
        FinancialBasicRequest(
            system_kw=5.0, annual_kwh=pv.annual_kwh, tariff_egp_per_kwh=2.0
        )
    )
    fin_mn = financial_basic.compute_financials(
        FinancialBasicRequest(
            system_kw=5.0, annual_kwh=mn.annual_kwh, tariff_egp_per_kwh=2.0
        )
    )

    # Both must pay back inside the horizon.
    assert fin_pv.discounted_payback_years is not None
    assert fin_mn.discounted_payback_years is not None
    # And land within ~25 % of each other — the two energy chains are
    # already constrained to within 15 % on annual kWh, and payback is
    # roughly linear in that figure for the parameter regime tested.
    delta = abs(fin_pv.discounted_payback_years - fin_mn.discounted_payback_years)
    larger = max(fin_pv.discounted_payback_years, fin_mn.discounted_payback_years)
    assert delta / larger < 0.25


# ─────────────── structural invariants on energy outputs ───────────────


@pytest.mark.parametrize(
    "module", [energy_pvlib, energy_manual], ids=["pvlib", "manual"]
)
def test_monthly_sum_equals_annual_to_floating_point_precision(module, fake_tmy):
    """Σ monthly_kwh == annual_kwh exactly (float-precision tolerance).

    Anything looser hides a real arithmetic bug — the two figures are
    derived from the same hourly series and there is no path by which
    they should disagree by more than rounding error.
    """
    sim = module.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)

    assert sum(sim.monthly_kwh) == pytest.approx(sim.annual_kwh, abs=1e-6)


@pytest.mark.parametrize(
    "module", [energy_pvlib, energy_manual], ids=["pvlib", "manual"]
)
def test_ac_hourly_is_non_negative(module, fake_tmy):
    """Per-hour AC must never be negative — the modules are passive
    consumers of irradiance, not loads. A negative entry would imply
    the array is *drawing* energy from the grid, which the financial
    model would silently turn into negative savings."""
    sim = module.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)

    arr = np.asarray(sim.ac_hourly.values, dtype=float)
    assert np.all(arr >= 0.0)


@pytest.mark.parametrize(
    "module", [energy_pvlib, energy_manual], ids=["pvlib", "manual"]
)
def test_ac_hourly_never_exceeds_inverter_nameplate(module, fake_tmy):
    """AC clipping at the inverter nameplate is the upper bound of the
    chain. With DC:AC = 1 and an arbitrary high-irradiance day, no
    hour of AC output can exceed the system's nameplate kW × 1 000 W."""
    sim = module.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)
    pdc0_w = 5.0 * 1000.0

    arr = np.asarray(sim.ac_hourly.values, dtype=float)
    # Allow one ULP of float slack.
    assert arr.max() <= pdc0_w + 1e-6


@pytest.mark.parametrize(
    "module", [energy_pvlib, energy_manual], ids=["pvlib", "manual"]
)
def test_simulation_is_deterministic(module, fake_tmy):
    """Two simulations with identical TMY + parameters must agree to
    bit-identical precision on every reported aggregate. Day 9's Monte
    Carlo engine relies on this: its only randomness must come from the
    parameter sampler, not from the kernel."""
    a = module.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)
    b = module.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)

    assert a.annual_kwh == b.annual_kwh
    assert a.monthly_kwh == b.monthly_kwh
    assert a.specific_yield_kwh_per_kwp == b.specific_yield_kwh_per_kwp
    assert a.capacity_factor == b.capacity_factor
    assert a.performance_ratio == b.performance_ratio
    assert a.poa_annual_kwh_per_m2 == b.poa_annual_kwh_per_m2
    assert a.mean_cell_temp_c == b.mean_cell_temp_c


@pytest.mark.parametrize(
    "module", [energy_pvlib, energy_manual], ids=["pvlib", "manual"]
)
def test_inverter_efficiency_is_monotone(module, fake_tmy):
    """Lower constant inverter efficiency must reduce annual AC by the
    same proportional factor (in the un-clipped regime). Guards against
    a sign / inversion bug where a *better* inverter would *reduce*
    output."""
    high = module.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0,
        inverter_efficiency=0.96,
    )
    low = module.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0,
        inverter_efficiency=0.85,
    )

    assert low.annual_kwh < high.annual_kwh
    # In the un-clipped regime, the ratio must equal the efficiency
    # ratio. fake_tmy has 500 W/m² constant GHI, so we can stay below
    # the inverter nameplate by construction — the ratio collapses to
    # 0.85 / 0.96 ≈ 0.885.
    expected_ratio = 0.85 / 0.96
    assert low.annual_kwh / high.annual_kwh == pytest.approx(expected_ratio, rel=5e-3)


# ─────────────── manual chain solar-geometry invariants ───────────────


def test_solar_position_handles_naive_datetime_index():
    """If a caller hands the manual chain a tz-naive DatetimeIndex
    (e.g. an offline test fixture), the geometry must still resolve
    correctly by treating timestamps as UTC. This guards the defensive
    fallback in :func:`energy_manual._solar_position`. PVGIS TMYs are
    always tz-aware, so the fallback only fires for unit-test inputs —
    but Day 9's Monte Carlo and Day 11's roof-detection synthesis may
    both build TMY-shaped frames in-memory."""
    naive = pd.DatetimeIndex(["2020-06-21T09:55:00"])
    aware = pd.DatetimeIndex(["2020-06-21T09:55:00"], tz="UTC")

    z_naive, az_naive = energy_manual._solar_position(naive, 30.0444, 31.2357)
    z_aware, az_aware = energy_manual._solar_position(aware, 30.0444, 31.2357)

    assert z_naive[0] == pytest.approx(z_aware[0])
    assert az_naive[0] == pytest.approx(az_aware[0])


def test_solar_zenith_in_valid_range_over_a_full_year():
    """Solar zenith must lie in [0°, 180°] at every TMY timestamp.
    Anything outside that band is a numerical defect (e.g. an unclipped
    arccos)."""
    idx = pd.date_range("2020-01-01", periods=8760, freq="h", tz="UTC")
    zen, az = energy_manual._solar_position(idx, 30.0444, 31.2357)

    assert zen.min() >= 0.0
    assert zen.max() <= 180.0
    assert az.min() >= 0.0
    assert az.max() < 360.0


def test_cell_temperature_meets_or_exceeds_air_temperature_in_sunlight():
    """The NOCT thermal model adds a non-negative term proportional to
    POA. So cell temp ≥ air temp at every hour where POA > 0 — and
    equals air temp exactly when POA = 0 (night)."""
    poa = np.array([0.0, 100.0, 500.0, 1000.0])
    air = np.array([20.0, 20.0, 20.0, 20.0])
    cell = energy_manual._cell_temperature_noct(poa_w_per_m2=poa, temp_air_c=air)

    assert cell[0] == pytest.approx(20.0)
    assert (cell[1:] >= 20.0).all()
    assert cell[3] > cell[2] > cell[1]  # strictly increasing in POA


# ─────────────── sizing × hardware override invariants ───────────────


def test_sizing_panel_count_is_monotone_in_roof_area():
    """A larger roof must support at least as many panels as a smaller
    one (with identical hardware). Anything else would mean the floor
    operation is non-monotone — a math regression."""
    smaller = pv_sizing.compute_system_size(SizingRequest(roof_area_m2=50.0))
    larger = pv_sizing.compute_system_size(SizingRequest(roof_area_m2=120.0))
    assert larger.panel_count >= smaller.panel_count
    assert larger.system_kw >= smaller.system_kw


def test_sizing_density_uses_actual_panel_rating_not_default():
    """When the caller overrides only ``panel_rated_watts``, the echoed
    ``panel_density_w_per_m2`` must use the override — not the config
    default. Guards against a partial-override regression where the
    density helper silently snaps back to the configured value."""
    result = pv_sizing.compute_system_size(
        SizingRequest(roof_area_m2=100.0, panel_rated_watts=600.0)
    )

    expected_density = (result.panel_count * 600.0) / result.usable_roof_area_m2
    assert result.panel_density_w_per_m2 == pytest.approx(expected_density)


def test_sizing_zero_utilization_overrides_are_rejected_by_pydantic():
    """Utilization is in (0, 1]. A zero or negative override is
    nonsense and must be rejected at the schema layer, not silently
    treated as "no usable roof"."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SizingRequest(roof_area_m2=100.0, roof_utilization_factor=0.0)
    with pytest.raises(ValidationError):
        SizingRequest(roof_area_m2=100.0, roof_utilization_factor=-0.1)


# ─────────────── financial structural identities ───────────────


def _zeroed_request(**overrides) -> FinancialBasicRequest:
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


def test_roi_equals_npv_over_capex_when_discount_zero():
    """At r = 0, the discounted NPV collapses to the cumulative
    cash-flow total, and the ROI percentage is exactly ``100 × NPV /
    capex``. A drift here means the two metrics have started using
    different cash-flow conventions."""
    result = financial_basic.compute_financials(_zeroed_request())
    expected_roi = 100.0 * result.npv_egp / result.capex_egp
    assert result.roi_percent == pytest.approx(expected_roi)


def test_year3_savings_matches_hand_derivation():
    """Year-3 savings = annual_kwh · (1−d)² · tariff · (1+i)².

    The day-by-day series test only pins year 1 and year 2; this guards
    against an off-by-one in the exponent (a regression that would
    pass year-1 and year-2 but bias longer horizons)."""
    request = _zeroed_request(
        tariff_inflation_rate=0.08,
        annual_degradation_rate=0.005,
    )
    result = financial_basic.compute_financials(request)
    expected_y3 = (
        8000.0 * (1.0 - 0.005) ** 2 * 2.0 * (1.0 + 0.08) ** 2
    )
    assert result.annual_savings_series_egp[2] == pytest.approx(expected_y3)


def test_cumulative_cashflow_strictly_increases_when_net_positive():
    """With year-1 net > 0 and zero degradation, every year contributes
    a strictly positive net cash flow, so the cumulative series after
    year 0 must be strictly monotone increasing."""
    result = financial_basic.compute_financials(
        _zeroed_request(tariff_inflation_rate=0.0, annual_degradation_rate=0.0)
    )
    series = result.cumulative_cashflow_series_egp
    deltas = [series[i + 1] - series[i] for i in range(1, len(series) - 1)]
    assert all(d > 0 for d in deltas)


def test_lcoe_break_even_identity_holds_when_tariff_is_constant():
    """LCOE is the *constant* tariff at which discounted cost equals
    discounted revenue, so at tariff = LCOE and tariff_inflation = 0,
    NPV must be zero (within rounding). This identity does **not** hold
    when the tariff escalates — LCOE then becomes a conservative
    lower bound, which is a separate (and non-trivial) finding worth
    reporting in the methodology chapter. See:

      Short, W., Packey, D. J., & Holt, T. (1995). *A manual for the
      economic evaluation of energy efficiency and renewable energy
      technologies.* NREL/TP-462-5173, §3.2.

    Pinning the *constant-tariff* identity catches a regression where
    LCOE and NPV drift onto different cash-flow conventions; the
    inflation-aware regime is then validated by separate behavioural
    tests (see ``test_npv_drops_when_discount_rate_increases`` etc.).
    """
    baseline = financial_basic.compute_financials(
        FinancialBasicRequest(
            system_kw=5.0,
            annual_kwh=8000.0,
            tariff_egp_per_kwh=2.0,
            tariff_inflation_rate=0.0,  # required for the identity
        )
    )

    at_lcoe = financial_basic.compute_financials(
        FinancialBasicRequest(
            system_kw=5.0,
            annual_kwh=8000.0,
            tariff_egp_per_kwh=baseline.lcoe_egp_per_kwh,
            cost_egp_per_kw=baseline.cost_egp_per_kw,
            analysis_period_years=baseline.analysis_period_years,
            discount_rate=baseline.discount_rate,
            tariff_inflation_rate=0.0,
            annual_degradation_rate=baseline.annual_degradation_rate,
            om_cost_fraction=baseline.om_cost_fraction,
        )
    )
    # NPV should land within rounding of zero on a 175 000-EGP capex —
    # i.e. effectively a 1e-4 relative tolerance.
    assert at_lcoe.npv_egp == pytest.approx(0.0, abs=baseline.capex_egp * 1e-4)


def test_financial_kernel_rejects_zero_horizon_at_service_layer():
    """The pydantic schema enforces ``analysis_period_years >= 1``, but
    the service is also defended for direct (un-validated) callers —
    e.g. the upcoming Monte Carlo engine that may call
    ``compute_financials`` with raw dataclass-like inputs in tight loops.
    Raising ``FinancialError`` rather than silently producing an empty
    series catches that misuse loudly."""

    class _RawRequest:
        system_kw = 5.0
        annual_kwh = 8000.0
        tariff_egp_per_kwh = 2.0
        cost_egp_per_kw = None
        analysis_period_years = 0  # pydantic would reject; we bypass it
        discount_rate = None
        tariff_inflation_rate = None
        annual_degradation_rate = None
        om_cost_fraction = None

    with pytest.raises(financial_basic.FinancialError):
        financial_basic.compute_financials(_RawRequest())  # type: ignore[arg-type]
