"""Schemas for the basic financial feasibility endpoint.

Day 6 deliberately exposes a *flat-tariff* financial model: capex,
year-1 savings, simple payback, discounted payback, NPV, LCOE, and the
full annual cash-flow series. Day 8 will add Egypt's tiered tariff
optimisation; Day 9 will wrap this same kernel in a Monte Carlo loop.
The shape below is therefore designed so that every "uncertain" knob
the Monte Carlo engine will perturb (degradation, tariff inflation,
discount rate, O&M, capex) is already a request-level parameter — the
deterministic and probabilistic chains share one set of inputs.

The result is intentionally verbose. Echoing every assumption used in
the calculation makes the JSON itself a self-auditing artefact for the
thesis: a reviewer can reproduce the math from the response alone,
without consulting either the server config or the request body.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FinancialBasicRequest(BaseModel):
    """Inputs for a flat-tariff financial feasibility calculation.

    All economic parameters are optional; omitting them falls back to the
    Egypt-tuned defaults in :pydata:`app.config.settings`. Requiring only
    ``system_kw``, ``annual_kwh``, and ``tariff_egp_per_kwh`` keeps the
    minimal call ergonomic for the frontend's first-pass dashboard.
    """

    system_kw: float = Field(..., gt=0, description="Nameplate DC capacity in kW")
    annual_kwh: float = Field(
        ...,
        gt=0,
        description=(
            "Year-1 AC energy delivered (kWh). Consume the value from "
            "either /api/energy/pvlib or /api/energy/manual."
        ),
    )
    tariff_egp_per_kwh: float = Field(
        ...,
        gt=0,
        description=(
            "Flat residential tariff in EGP per kWh. Day 8 will introduce "
            "a tiered-tariff model that supersedes this for Egyptian "
            "households."
        ),
    )

    cost_egp_per_kw: float | None = Field(
        None,
        gt=0,
        description=(
            "Installed system cost in EGP per kW of DC capacity "
            "(default: configured Egypt market 2024 value)."
        ),
    )
    analysis_period_years: int | None = Field(
        None,
        ge=1,
        le=50,
        description="Analysis horizon in years (default: configured 25-year module warranty term).",
    )
    discount_rate: float | None = Field(
        None,
        ge=0,
        lt=1,
        description="Annual real discount rate, fraction (default: configured 0.04).",
    )
    tariff_inflation_rate: float | None = Field(
        None,
        ge=0,
        lt=1,
        description=(
            "Annual real tariff escalation, fraction. Default: configured "
            "0.08 (EgyptERA decade trend)."
        ),
    )
    annual_degradation_rate: float | None = Field(
        None,
        ge=0,
        lt=1,
        description=(
            "Per-year fractional drop in module output. Default: "
            "configured 0.005 (NREL median for mono-Si)."
        ),
    )
    om_cost_fraction: float | None = Field(
        None,
        ge=0,
        lt=1,
        description=(
            "Annual O&M cost as a fraction of capex. Default: configured "
            "0.01 (IRENA residential rooftop benchmark)."
        ),
    )


class FinancialBasicResult(BaseModel):
    """Headline output of the flat-tariff financial calculation.

    Includes both a "textbook simple payback" (capex divided by year-1
    savings, the number every PV brochure quotes) and a
    "discounted payback" that accounts for time value of money,
    degradation, tariff inflation, and O&M — the figure a financial
    analyst would actually use. Reporting both makes the gap between
    them visible, which is itself a methodological point.
    """

    capex_egp: float = Field(..., description="Total upfront installed system cost in EGP.")
    annual_savings_year1_egp: float = Field(
        ...,
        description=(
            "First-year electricity-bill savings (annual_kwh × tariff). "
            "Subsequent years are escalated by tariff inflation and "
            "reduced by module degradation."
        ),
    )
    simple_payback_years: float | None = Field(
        ...,
        description=(
            "Capex divided by year-1 net savings (savings − O&M). None "
            "when the system never recovers its capex within the analysis "
            "period."
        ),
    )
    discounted_payback_years: float | None = Field(
        ...,
        description=(
            "Year at which discounted cumulative cash flow first turns "
            "non-negative, with linear interpolation. None when not "
            "recovered within the analysis period."
        ),
    )
    npv_egp: float = Field(
        ...,
        description=(
            "Net present value of the project over the analysis period. "
            "Positive ⇒ investment is worthwhile at the chosen discount rate."
        ),
    )
    lcoe_egp_per_kwh: float = Field(
        ...,
        description=(
            "Levelised cost of electricity: discounted total cost divided "
            "by discounted total generation. The break-even tariff at "
            "which NPV would be zero."
        ),
    )
    roi_percent: float = Field(
        ...,
        description=(
            "Lifetime return on investment: 100 × (lifetime_savings − "
            "lifetime_om − capex) / capex."
        ),
    )
    lifetime_savings_egp: float = Field(
        ...,
        description="Sum of nominal (un-discounted) annual savings over the analysis period.",
    )
    lifetime_om_egp: float = Field(
        ...,
        description="Sum of nominal (un-discounted) annual O&M costs over the analysis period.",
    )
    lifetime_generation_kwh: float = Field(
        ...,
        description="Sum of degraded annual generation over the analysis period.",
    )

    annual_savings_series_egp: list[float] = Field(
        ...,
        description="Year-by-year savings (length = analysis_period_years).",
    )
    cumulative_cashflow_series_egp: list[float] = Field(
        ...,
        description=(
            "Cumulative un-discounted cash flow, starting at -capex in "
            "year 0 (length = analysis_period_years + 1)."
        ),
    )

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
