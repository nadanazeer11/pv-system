"""Flat-tariff financial feasibility model.

This is Day 6 of the plan: the *baseline* economic kernel. It takes a
year-1 generation figure (from either the pvlib or the manual energy
chain) and answers the bachelor-thesis dashboard's headline questions:

    * How much does the system cost?
    * How much does it save in year 1?
    * In how many years does the household break even (with and without
      time value of money)?
    * What is the project NPV?
    * What is the levelised cost per kWh?

A *flat* tariff is used by design — Egypt's residential bills are
actually billed on a progressive tier structure (EgyptERA), and the
thesis's second contribution is to model that explicitly in Day 8's
``tiered_tariff`` service. Day 9's Monte Carlo engine will also reuse
the same kernel below, perturbing each parameter by its uncertainty
distribution to produce a confidence interval around payback.

Conventions
-----------
* All currency in EGP. All energy in kWh. All rates as decimal
  fractions, never percentages.
* Year indexing: year ``0`` is the moment of installation (capex paid).
  Year ``1`` is the first full year of operation (first savings, first
  O&M, first 0.5 % degradation step relative to nameplate).
* Generation in year ``t`` (1-based): ``annual_kwh × (1 − d)^(t−1)``.
* Tariff in year ``t``: ``tariff × (1 + i)^(t−1)``.
* Discounting: ``1 / (1 + r)^t`` applied to year-``t`` cash flows.
* Payback by linear interpolation between the last negative and first
  non-negative cumulative cash flow.

Why include NPV / LCOE in a "basic" model?
------------------------------------------
Simple payback alone is widely criticised in the energy-finance
literature for ignoring the time value of money and the post-payback
period — yet it is the single number every PV brochure quotes. A
defensible thesis must report it (so the result is comparable to the
literature and to consumer-facing tools) **and** report NPV/LCOE/
discounted payback alongside, so the reader can see the gap that the
naïve metric hides. The basic model therefore returns both.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.schemas.financial import FinancialBasicRequest, FinancialBasicResult


class FinancialError(ValueError):
    """Raised when financial inputs are economically nonsensical."""


@dataclass(frozen=True)
class FinancialBasic:
    """Internal computation result.

    A dataclass mirror of :class:`FinancialBasicResult` so the service
    can be unit-tested without going through Pydantic validation. The
    router translates between the two.
    """

    capex_egp: float
    annual_savings_year1_egp: float
    simple_payback_years: float | None
    discounted_payback_years: float | None
    npv_egp: float
    lcoe_egp_per_kwh: float
    roi_percent: float
    lifetime_savings_egp: float
    lifetime_om_egp: float
    lifetime_generation_kwh: float
    annual_savings_series_egp: list[float]
    cumulative_cashflow_series_egp: list[float]
    # Echoed assumptions
    system_kw: float
    annual_kwh: float
    tariff_egp_per_kwh: float
    cost_egp_per_kw: float
    analysis_period_years: int
    discount_rate: float
    tariff_inflation_rate: float
    annual_degradation_rate: float
    om_cost_fraction: float


def _interpolated_payback(cumulative: list[float]) -> float | None:
    """Find the year at which a cumulative cash-flow series first turns
    non-negative, with linear interpolation between bracketing years.

    ``cumulative[0]`` corresponds to year 0 (negative capex) and
    ``cumulative[t]`` is the cumulative cash flow after year ``t``.
    Returns ``None`` if the series never reaches zero — the project does
    not pay back within the analysis horizon.

    Linear interpolation is the conventional textbook treatment: the
    cash-flow magnitudes are large enough relative to one annual step
    that intra-year compounding effects are below the rounding precision
    a homeowner would care about (months, not days).
    """
    for t in range(1, len(cumulative)):
        if cumulative[t] >= 0:
            previous = cumulative[t - 1]
            current = cumulative[t]
            if current == previous:
                return float(t)
            # Fraction of the year needed to close the remaining gap.
            fraction = -previous / (current - previous)
            return (t - 1) + fraction
    return None


def compute_financials(request: FinancialBasicRequest) -> FinancialBasic:
    """Run the full flat-tariff financial calculation.

    Parameters
    ----------
    request : FinancialBasicRequest
        System size, year-1 energy, flat tariff, plus optional economic
        overrides. Any field left as ``None`` falls back to the Egypt-
        tuned defaults in :pydata:`app.config.settings`.

    Returns
    -------
    FinancialBasic
        All headline metrics plus the year-by-year cash-flow series so
        the frontend can render a payback chart without re-running the
        kernel.

    Raises
    ------
    FinancialError
        If the resolved analysis period is non-positive (caught at the
        schema layer for Pydantic-validated calls, but defended here so
        the service is safe to import standalone).
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

    if analysis_years < 1:
        raise FinancialError("analysis_period_years must be at least 1")

    capex = request.system_kw * cost_egp_per_kw
    annual_om = capex * om_fraction

    annual_savings: list[float] = []
    annual_generation: list[float] = []
    annual_net_cashflow: list[float] = []  # savings − O&M (no capex)
    discounted_savings_minus_om = 0.0
    discounted_om = 0.0
    discounted_generation = 0.0

    for year in range(1, analysis_years + 1):
        gen_t = request.annual_kwh * (1.0 - degradation) ** (year - 1)
        tariff_t = request.tariff_egp_per_kwh * (1.0 + tariff_inflation) ** (year - 1)
        savings_t = gen_t * tariff_t
        net_t = savings_t - annual_om
        annual_generation.append(gen_t)
        annual_savings.append(savings_t)
        annual_net_cashflow.append(net_t)

        discount_factor = (1.0 + discount_rate) ** year
        discounted_savings_minus_om += net_t / discount_factor
        discounted_om += annual_om / discount_factor
        discounted_generation += gen_t / discount_factor

    npv = -capex + discounted_savings_minus_om

    # LCOE: total discounted cost / total discounted generation. Capex
    # is in year-0 EGP and therefore enters un-discounted; O&M is
    # already discounted to year 0.
    if discounted_generation > 0:
        lcoe = (capex + discounted_om) / discounted_generation
    else:
        # Degenerate case (year-1 generation already zero or 100 %
        # degradation in one step): mark LCOE as infinite-equivalent.
        lcoe = float("inf")

    lifetime_savings = sum(annual_savings)
    lifetime_om = annual_om * analysis_years
    lifetime_generation = sum(annual_generation)

    if capex > 0:
        roi_percent = 100.0 * (lifetime_savings - lifetime_om - capex) / capex
    else:
        roi_percent = float("inf")

    # Simple payback: classical textbook form. Uses year-1 net savings
    # (savings minus O&M). No inflation, no degradation, no discounting.
    year1_net = annual_savings[0] - annual_om
    if year1_net > 0:
        simple_payback = capex / year1_net
        if simple_payback > analysis_years:
            simple_payback = None  # fails to recover within horizon
    else:
        simple_payback = None

    # Cumulative un-discounted cash flow including capex at year 0.
    cumulative: list[float] = [-capex]
    running = -capex
    for net in annual_net_cashflow:
        running += net
        cumulative.append(running)

    # Discounted cumulative (for discounted payback). Starts at -capex
    # because year-0 capex is already in present-value terms.
    discounted_cumulative: list[float] = [-capex]
    running_disc = -capex
    for year_idx, net in enumerate(annual_net_cashflow, start=1):
        running_disc += net / (1.0 + discount_rate) ** year_idx
        discounted_cumulative.append(running_disc)

    discounted_payback = _interpolated_payback(discounted_cumulative)

    return FinancialBasic(
        capex_egp=capex,
        annual_savings_year1_egp=annual_savings[0],
        simple_payback_years=simple_payback,
        discounted_payback_years=discounted_payback,
        npv_egp=npv,
        lcoe_egp_per_kwh=lcoe,
        roi_percent=roi_percent,
        lifetime_savings_egp=lifetime_savings,
        lifetime_om_egp=lifetime_om,
        lifetime_generation_kwh=lifetime_generation,
        annual_savings_series_egp=annual_savings,
        cumulative_cashflow_series_egp=cumulative,
        system_kw=request.system_kw,
        annual_kwh=request.annual_kwh,
        tariff_egp_per_kwh=request.tariff_egp_per_kwh,
        cost_egp_per_kw=cost_egp_per_kw,
        analysis_period_years=analysis_years,
        discount_rate=discount_rate,
        tariff_inflation_rate=tariff_inflation,
        annual_degradation_rate=degradation,
        om_cost_fraction=om_fraction,
    )


def to_result(model: FinancialBasic) -> FinancialBasicResult:
    """Translate the internal dataclass into the response schema."""
    return FinancialBasicResult(
        capex_egp=model.capex_egp,
        annual_savings_year1_egp=model.annual_savings_year1_egp,
        simple_payback_years=model.simple_payback_years,
        discounted_payback_years=model.discounted_payback_years,
        npv_egp=model.npv_egp,
        lcoe_egp_per_kwh=model.lcoe_egp_per_kwh,
        roi_percent=model.roi_percent,
        lifetime_savings_egp=model.lifetime_savings_egp,
        lifetime_om_egp=model.lifetime_om_egp,
        lifetime_generation_kwh=model.lifetime_generation_kwh,
        annual_savings_series_egp=model.annual_savings_series_egp,
        cumulative_cashflow_series_egp=model.cumulative_cashflow_series_egp,
        system_kw=model.system_kw,
        annual_kwh=model.annual_kwh,
        tariff_egp_per_kwh=model.tariff_egp_per_kwh,
        cost_egp_per_kw=model.cost_egp_per_kw,
        analysis_period_years=model.analysis_period_years,
        discount_rate=model.discount_rate,
        tariff_inflation_rate=model.tariff_inflation_rate,
        annual_degradation_rate=model.annual_degradation_rate,
        om_cost_fraction=model.om_cost_fraction,
    )
