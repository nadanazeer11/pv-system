"""EgyptERA tiered-tariff billing kernel and PV-size optimizer.

This module implements the second of the thesis's three contributions
(Contribution B in PLAN.md): a bill calculator and system-size
optimizer that respect Egypt's *progressive marginal block* residential
tariff. The kernel answers two questions a flat-tariff calculator
cannot:

1. **What does the next saved kWh actually save?** Under the EgyptERA
   schedule, that depends on the household's *current* monthly
   consumption — savings come off the top tier first, so a high
   consumer recoups generation at 1.55 EGP/kWh while a low consumer
   recoups at 0.58 EGP/kWh.
2. **What size system actually maximises lifetime household NPV?**
   Once consumption is pulled down into the cheap tiers, additional
   generation has near-zero value (assuming zero export credit, which
   matches the conservative Egypt residential default). Sizing the
   system to fit the *expensive* tiers — not to maximise generation —
   is the economically correct move.

Why the progressive *marginal* interpretation?
---------------------------------------------
Egypt's official EgyptERA schedule is widely reported in two forms in
the consumer-facing press:

* **Inclusive** — exceeding a threshold reverts the *whole* month's
  consumption to the higher tier. This penalises consumers who drift
  one kWh over a band edge.
* **Marginal** — each band charges only the kWh that fall inside it
  (the canonical "progressive" tariff used in most economics texts).

The official EgyptERA bill statement uses the marginal interpretation
(tier amounts on the bill add up to the total). We adopt that here:

* It matches the published bill format.
* It is the conservative choice for the *PV value* claim — under an
  inclusive schedule PV would look even *more* valuable, since saving
  one kWh near a band edge could shift the whole month down a tier.
  Choosing the marginal schedule means our payback claims hold under
  the worst of the two reasonable readings.

References
----------
* EgyptERA published residential schedule effective August 2023.
* Esmail & Negm (2021), *Techno-economic analysis of grid-tied PV in
  Egypt*, J. of Renewable Energy: discusses tier-aware sizing without
  publishing optimization curves — the gap this module fills.
* IRENA (2023) Renewable Power Generation Costs: O&M and capex
  benchmarks for residential rooftop PV.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.schemas.tariff import (
    MonthlyBillBreakdown,
    OptimizationCandidate,
    TariffBillRequest,
    TariffBillResult,
    TariffOptimizeRequest,
    TariffOptimizeResult,
    TariffSavingsRequest,
    TariffSavingsResult,
    TariffTier,
)


class TariffError(ValueError):
    """Raised when a tariff calculation receives economically nonsensical input."""


# ─────────────────────────── Tier resolution ───────────────────────────


def _resolve_tiers(override: list[TariffTier] | None) -> list[TariffTier]:
    """Return the tier schedule to use: caller override, else config default.

    The configured default is materialised into ``TariffTier`` objects
    here rather than at import time, so a settings reload (env var
    flip in tests) is honoured immediately.
    """
    if override is not None:
        return list(override)
    return [
        TariffTier(upper_kwh_per_month=upper, egp_per_kwh=price)
        for upper, price in settings.egypt_residential_tariff_tiers
    ]


# ──────────────────────── Single-month billing ─────────────────────────


@dataclass(frozen=True)
class _MonthBill:
    """Per-month decomposition of a progressive-marginal bill.

    Internal mirror of :class:`MonthlyBillBreakdown` so the service can
    be exercised without going through Pydantic.
    """

    consumption_kwh: float
    bill_egp: float
    per_tier_kwh: list[float]
    per_tier_egp: list[float]
    marginal_tariff_egp_per_kwh: float


def _bill_one_month(
    consumption_kwh: float,
    tiers: list[TariffTier],
) -> _MonthBill:
    """Bill a single month under a progressive-marginal schedule.

    Walks the tiers in order, charging the consumption that falls inside
    each band at that band's marginal rate. The "marginal tariff"
    returned is the rate of the highest tier that received any kWh —
    the price at which the *next* kWh (i.e. the next kWh of PV
    generation) would be displaced.

    Boundary conventions
    --------------------
    * A band ``(upper, price)`` covers the half-open interval
      ``(prev_upper, upper]``. Consumption exactly on a boundary is
      attributed to the lower band.
    * If ``consumption_kwh == 0`` the marginal tariff is the price of
      the *first* band — the rate the household would pay for its
      first kWh. This avoids reporting "0 EGP/kWh marginal" for a zero-
      consumption month, which would be silently wrong for downstream
      consumers asking "what does the next kWh save?".
    """
    if consumption_kwh < 0:
        raise TariffError("consumption_kwh must be non-negative")
    if not tiers:
        raise TariffError("tiers must not be empty")

    per_tier_kwh = [0.0] * len(tiers)
    per_tier_egp = [0.0] * len(tiers)
    bill = 0.0
    remaining = consumption_kwh
    previous_upper = 0.0
    highest_tier_used = 0  # zero-based index of the most expensive band touched

    for idx, tier in enumerate(tiers):
        band_capacity = tier.upper_kwh_per_month - previous_upper
        if band_capacity < 0:
            raise TariffError("tier upper bounds must be non-decreasing")

        if remaining <= 0:
            break

        kwh_in_band = min(remaining, band_capacity)
        cost_in_band = kwh_in_band * tier.egp_per_kwh
        per_tier_kwh[idx] = kwh_in_band
        per_tier_egp[idx] = cost_in_band
        bill += cost_in_band
        remaining -= kwh_in_band
        previous_upper = tier.upper_kwh_per_month

        if kwh_in_band > 0:
            highest_tier_used = idx

    if remaining > 1e-9:
        # Final band must be unbounded (or its capacity must cover the rest).
        # If the schedule's final upper bound is too small, the caller passed
        # a malformed schedule.
        raise TariffError(
            "consumption exceeds the final tier's upper bound; the last "
            "band of a residential schedule must cover all 'and above' kWh"
        )

    if consumption_kwh == 0:
        marginal = tiers[0].egp_per_kwh
    else:
        marginal = tiers[highest_tier_used].egp_per_kwh

    return _MonthBill(
        consumption_kwh=consumption_kwh,
        bill_egp=bill,
        per_tier_kwh=per_tier_kwh,
        per_tier_egp=per_tier_egp,
        marginal_tariff_egp_per_kwh=marginal,
    )


def _to_breakdown(month_index: int, b: _MonthBill) -> MonthlyBillBreakdown:
    """Translate the internal dataclass to its Pydantic counterpart."""
    return MonthlyBillBreakdown(
        month_index=month_index,
        consumption_kwh=b.consumption_kwh,
        bill_egp=b.bill_egp,
        per_tier_kwh=b.per_tier_kwh,
        per_tier_egp=b.per_tier_egp,
        marginal_tariff_egp_per_kwh=b.marginal_tariff_egp_per_kwh,
    )


# ───────────────────────── Annual bill (12 months) ─────────────────────


def compute_bill(request: TariffBillRequest) -> TariffBillResult:
    """Bill a 12-month consumption profile under a tiered schedule.

    The annual bill is the sum of twelve independent monthly bills;
    Egypt's residential tariff resets every billing cycle, so monthly
    consumption is the right granularity. Aggregating to annual kWh and
    billing once would *understate* the bill for a peaky consumer (e.g.
    a household that uses 1 200 kWh in summer and 200 kWh in winter)
    because it would smear the summer over the cheap winter tiers.
    """
    tiers = _resolve_tiers(request.tiers)

    months = [
        _bill_one_month(c, tiers) for c in request.monthly_consumption_kwh
    ]
    breakdown = [_to_breakdown(i + 1, m) for i, m in enumerate(months)]

    annual_consumption = sum(request.monthly_consumption_kwh)
    annual_bill = sum(m.bill_egp for m in months)
    average = annual_bill / annual_consumption if annual_consumption > 0 else 0.0

    return TariffBillResult(
        annual_bill_egp=annual_bill,
        annual_consumption_kwh=annual_consumption,
        average_tariff_egp_per_kwh=average,
        monthly_breakdown=breakdown,
        tiers=tiers,
    )


# ───────────────────────── Savings under PV ────────────────────────────


@dataclass(frozen=True)
class _SavingsModel:
    """Internal result of a savings calculation, before Pydantic translation."""

    bill_before_egp: float
    bill_after_egp: float
    annual_savings_egp: float
    self_consumed_kwh: float
    exported_kwh: float
    export_credit_egp: float
    average_savings_egp_per_kwh: float
    monthly_bill_before: list[_MonthBill]
    monthly_bill_after: list[_MonthBill]


def _compute_savings_model(
    monthly_consumption_kwh: list[float],
    monthly_generation_kwh: list[float],
    tiers: list[TariffTier],
    export_credit_egp_per_kwh: float,
) -> _SavingsModel:
    """Bill before/after PV netting, return the delta.

    Self-consumption is modelled month-by-month: generation that
    exceeds that month's consumption spills into the export pool and
    earns ``export_credit_egp_per_kwh`` per kWh, while the netted
    consumption (``max(0, consumption − generation)``) is billed
    against the tier schedule.

    Egypt's current residential net-metering scheme reimburses surplus
    generation at the *lowest* tier rate (sometimes zero). The default
    of zero is therefore the conservative choice for the thesis: any
    payback figure quoted under the default model holds under the
    least favourable export rules.
    """
    months_before: list[_MonthBill] = []
    months_after: list[_MonthBill] = []
    total_self = 0.0
    total_export = 0.0

    for c, g in zip(monthly_consumption_kwh, monthly_generation_kwh):
        before = _bill_one_month(c, tiers)
        netted = max(0.0, c - g)
        after = _bill_one_month(netted, tiers)
        self_cons = min(c, g)
        export = max(0.0, g - c)
        months_before.append(before)
        months_after.append(after)
        total_self += self_cons
        total_export += export

    bill_before = sum(m.bill_egp for m in months_before)
    bill_after = sum(m.bill_egp for m in months_after)
    export_credit = total_export * export_credit_egp_per_kwh
    annual_savings = bill_before - bill_after + export_credit
    total_generation = total_self + total_export
    average_savings = (
        annual_savings / total_generation if total_generation > 0 else 0.0
    )

    return _SavingsModel(
        bill_before_egp=bill_before,
        bill_after_egp=bill_after,
        annual_savings_egp=annual_savings,
        self_consumed_kwh=total_self,
        exported_kwh=total_export,
        export_credit_egp=export_credit,
        average_savings_egp_per_kwh=average_savings,
        monthly_bill_before=months_before,
        monthly_bill_after=months_after,
    )


def compute_savings(request: TariffSavingsRequest) -> TariffSavingsResult:
    """Public Pydantic wrapper around :func:`_compute_savings_model`."""
    tiers = _resolve_tiers(request.tiers)
    export_credit = (
        request.export_credit_egp_per_kwh
        if request.export_credit_egp_per_kwh is not None
        else 0.0
    )
    model = _compute_savings_model(
        monthly_consumption_kwh=request.monthly_consumption_kwh,
        monthly_generation_kwh=request.monthly_generation_kwh,
        tiers=tiers,
        export_credit_egp_per_kwh=export_credit,
    )
    return TariffSavingsResult(
        bill_before_egp=model.bill_before_egp,
        bill_after_egp=model.bill_after_egp,
        annual_savings_egp=model.annual_savings_egp,
        self_consumed_kwh=model.self_consumed_kwh,
        exported_kwh=model.exported_kwh,
        export_credit_egp=model.export_credit_egp,
        average_savings_egp_per_kwh=model.average_savings_egp_per_kwh,
        monthly_bill_before=[
            _to_breakdown(i + 1, m) for i, m in enumerate(model.monthly_bill_before)
        ],
        monthly_bill_after=[
            _to_breakdown(i + 1, m) for i, m in enumerate(model.monthly_bill_after)
        ],
    )


# ─────────────────────────── Size optimization ─────────────────────────


def _npv_for_size(
    *,
    system_kw: float,
    baseline_kw: float,
    baseline_monthly_generation_kwh: list[float],
    monthly_consumption_kwh: list[float],
    tiers: list[TariffTier],
    export_credit_egp_per_kwh: float,
    cost_egp_per_kw: float,
    analysis_years: int,
    discount_rate: float,
    tariff_inflation: float,
    degradation: float,
    om_fraction: float,
) -> tuple[float, float, float, float | None, float | None]:
    """NPV/payback for one candidate system size.

    Returns ``(annual_generation_year1, year1_savings, npv,
    simple_payback, discounted_payback)``.

    Modelling notes
    ---------------
    * Generation scales linearly with ``system_kw / baseline_kw``: the
      size sweep does not re-run the energy chain. For residential
      roof-mounted systems sized within an order of magnitude of the
      baseline, this is the standard rule-of-thumb in the industry —
      ground-cover-ratio shading effects only become material at much
      larger plant sizes.
    * Year-``t`` generation: ``year1 × (1 − degradation)^(t−1)``.
    * Year-``t`` tier prices: every tier rate scaled by
      ``(1 + tariff_inflation)^(t−1)``. EgyptERA's history of nominal
      reform increments suggests the *whole* schedule shifts together,
      not one tier at a time, so a uniform scalar is the right
      first-order model.
    * Monthly consumption is held constant across years. Consumption
      growth is a documented limitation of the basic model; Day 9's
      Monte Carlo engine will treat it as a stochastic input.
    """
    capex = system_kw * cost_egp_per_kw
    annual_om = capex * om_fraction

    scale = system_kw / baseline_kw if baseline_kw > 0 else 0.0
    generation_year1 = [g * scale for g in baseline_monthly_generation_kwh]
    annual_gen_year1 = sum(generation_year1)

    annual_savings_series: list[float] = []
    discounted_net = 0.0
    cumulative = -capex
    cumulative_disc = -capex
    simple_payback: float | None = None
    discounted_payback: float | None = None

    year1_savings = 0.0
    for year in range(1, analysis_years + 1):
        # Inflate every tier price for this year.
        inflation = (1.0 + tariff_inflation) ** (year - 1)
        priced_tiers = [
            TariffTier(
                upper_kwh_per_month=t.upper_kwh_per_month,
                egp_per_kwh=t.egp_per_kwh * inflation,
            )
            for t in tiers
        ]
        # Degrade generation for this year.
        deg = (1.0 - degradation) ** (year - 1)
        generation_year_t = [g * deg for g in generation_year1]

        savings_model = _compute_savings_model(
            monthly_consumption_kwh=monthly_consumption_kwh,
            monthly_generation_kwh=generation_year_t,
            tiers=priced_tiers,
            export_credit_egp_per_kwh=export_credit_egp_per_kwh * inflation,
        )
        savings = savings_model.annual_savings_egp
        net = savings - annual_om
        annual_savings_series.append(savings)
        if year == 1:
            year1_savings = savings

        prev_cum = cumulative
        cumulative += net
        if simple_payback is None and prev_cum < 0 <= cumulative:
            denom = cumulative - prev_cum
            if denom != 0:
                simple_payback = (year - 1) + (-prev_cum / denom)
            else:
                simple_payback = float(year)

        df = (1.0 + discount_rate) ** year
        discounted_net += net / df
        prev_cum_disc = cumulative_disc
        cumulative_disc += net / df
        if discounted_payback is None and prev_cum_disc < 0 <= cumulative_disc:
            denom = cumulative_disc - prev_cum_disc
            if denom != 0:
                discounted_payback = (year - 1) + (-prev_cum_disc / denom)
            else:
                discounted_payback = float(year)

    npv = -capex + discounted_net
    return annual_gen_year1, year1_savings, npv, simple_payback, discounted_payback


def optimize_system_size(request: TariffOptimizeRequest) -> TariffOptimizeResult:
    """Sweep system sizes and return the NPV-maximising kW.

    The sweep is a deterministic grid search: ``ceil(max_kw /
    grid_step_kw) + 1`` candidate sizes from 0 to ``max_system_kw``.
    A grid search is preferred over closed-form optimisation because
    the tier structure makes the NPV-vs-size curve non-smooth — each
    tier boundary that a candidate system pulls the household across
    introduces a kink. Continuous-derivative methods would mis-locate
    the optimum at those kinks, while the grid-search resolution is
    set by ``grid_step_kw`` (default 0.5 kW ≈ one panel).
    """
    cost_egp_per_kw = (
        request.cost_egp_per_kw
        if request.cost_egp_per_kw is not None
        else settings.installed_cost_egp_per_kw
    )
    analysis_years = (
        request.analysis_period_years
        if request.analysis_period_years is not None
        else settings.analysis_period_years
    )
    discount_rate = (
        request.discount_rate
        if request.discount_rate is not None
        else settings.discount_rate
    )
    tariff_inflation = (
        request.tariff_inflation_rate
        if request.tariff_inflation_rate is not None
        else settings.tariff_inflation_rate
    )
    degradation = (
        request.annual_degradation_rate
        if request.annual_degradation_rate is not None
        else settings.annual_degradation_rate
    )
    om_fraction = (
        request.om_cost_fraction
        if request.om_cost_fraction is not None
        else settings.om_cost_fraction
    )
    export_credit = (
        request.export_credit_egp_per_kwh
        if request.export_credit_egp_per_kwh is not None
        else 0.0
    )

    if analysis_years < 1:
        raise TariffError("analysis_period_years must be at least 1")
    if request.max_system_kw <= 0:
        raise TariffError("max_system_kw must be positive")
    if request.grid_step_kw <= 0:
        raise TariffError("grid_step_kw must be positive")

    tiers = _resolve_tiers(request.tiers)

    candidates: list[OptimizationCandidate] = []
    best_npv = float("-inf")
    best_idx = 0
    n_steps = int(request.max_system_kw / request.grid_step_kw)
    sizes = [i * request.grid_step_kw for i in range(n_steps + 1)]
    if sizes[-1] < request.max_system_kw - 1e-9:
        sizes.append(request.max_system_kw)

    for size in sizes:
        if size <= 0:
            candidates.append(
                OptimizationCandidate(
                    system_kw=0.0,
                    annual_generation_kwh=0.0,
                    year1_savings_egp=0.0,
                    capex_egp=0.0,
                    npv_egp=0.0,
                    simple_payback_years=None,
                    discounted_payback_years=None,
                )
            )
            if 0.0 > best_npv:
                best_npv = 0.0
                best_idx = len(candidates) - 1
            continue

        gen, year1_save, npv, simple_pb, disc_pb = _npv_for_size(
            system_kw=size,
            baseline_kw=request.baseline_system_kw,
            baseline_monthly_generation_kwh=request.baseline_monthly_generation_kwh,
            monthly_consumption_kwh=request.monthly_consumption_kwh,
            tiers=tiers,
            export_credit_egp_per_kwh=export_credit,
            cost_egp_per_kw=cost_egp_per_kw,
            analysis_years=analysis_years,
            discount_rate=discount_rate,
            tariff_inflation=tariff_inflation,
            degradation=degradation,
            om_fraction=om_fraction,
        )
        capex = size * cost_egp_per_kw
        candidates.append(
            OptimizationCandidate(
                system_kw=size,
                annual_generation_kwh=gen,
                year1_savings_egp=year1_save,
                capex_egp=capex,
                npv_egp=npv,
                simple_payback_years=simple_pb,
                discounted_payback_years=disc_pb,
            )
        )
        if npv > best_npv:
            best_npv = npv
            best_idx = len(candidates) - 1

    best = candidates[best_idx]

    # Counterfactual: what would a flat-tariff model recommend?
    # Use the household's *average* tariff (annual bill ÷ annual kWh).
    bill_before = compute_bill(
        TariffBillRequest(
            monthly_consumption_kwh=request.monthly_consumption_kwh,
            tiers=tiers,
        )
    )
    flat_optimum_kw = _flat_tariff_optimum_kw(
        candidates=candidates,
        baseline_kw=request.baseline_system_kw,
        baseline_monthly_generation_kwh=request.baseline_monthly_generation_kwh,
        flat_tariff=bill_before.average_tariff_egp_per_kwh,
        cost_egp_per_kw=cost_egp_per_kw,
        analysis_years=analysis_years,
        discount_rate=discount_rate,
        tariff_inflation=tariff_inflation,
        degradation=degradation,
        om_fraction=om_fraction,
    )

    return TariffOptimizeResult(
        optimal_system_kw=best.system_kw,
        optimal_npv_egp=best.npv_egp,
        optimal_year1_savings_egp=best.year1_savings_egp,
        optimal_simple_payback_years=best.simple_payback_years,
        optimal_discounted_payback_years=best.discounted_payback_years,
        flat_tariff_optimum_kw=flat_optimum_kw,
        candidates=candidates,
        tiers=tiers,
        analysis_period_years=analysis_years,
        discount_rate=discount_rate,
        tariff_inflation_rate=tariff_inflation,
        annual_degradation_rate=degradation,
        om_cost_fraction=om_fraction,
        cost_egp_per_kw=cost_egp_per_kw,
        export_credit_egp_per_kwh=export_credit,
    )


def _flat_tariff_optimum_kw(
    *,
    candidates: list[OptimizationCandidate],
    baseline_kw: float,
    baseline_monthly_generation_kwh: list[float],
    flat_tariff: float,
    cost_egp_per_kw: float,
    analysis_years: int,
    discount_rate: float,
    tariff_inflation: float,
    degradation: float,
    om_fraction: float,
) -> float:
    """NPV-maximising size *if* the household believed the tariff were flat.

    Reported alongside the tier-aware optimum so the dashboard can
    highlight Contribution B's effect: the flat model typically
    over-sizes the system, because it values every saved kWh at the
    average rate even after consumption has been pulled down into the
    cheap tiers.

    Walks the same candidate grid the tier-aware optimizer used so the
    two figures are strictly comparable (same discretisation, same
    discounting, same degradation).
    """
    annual_gen_baseline = sum(baseline_monthly_generation_kwh)
    best_kw = 0.0
    best_npv = 0.0
    for cand in candidates:
        size = cand.system_kw
        capex = size * cost_egp_per_kw
        annual_om = capex * om_fraction
        scale = size / baseline_kw if baseline_kw > 0 else 0.0
        gen_year1 = annual_gen_baseline * scale
        discounted_net = 0.0
        for year in range(1, analysis_years + 1):
            gen_t = gen_year1 * (1.0 - degradation) ** (year - 1)
            tariff_t = flat_tariff * (1.0 + tariff_inflation) ** (year - 1)
            net = gen_t * tariff_t - annual_om
            discounted_net += net / (1.0 + discount_rate) ** year
        npv = -capex + discounted_net
        if npv > best_npv:
            best_npv = npv
            best_kw = size
    return best_kw
