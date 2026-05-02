"""Schemas for the one-at-a-time sensitivity (tornado) endpoint.

Day 18's second deliverable answers the methodology question
"which input matters most?". The endpoint runs a deterministic
*one-at-a-time* (OAT) sensitivity sweep around the baseline financial
scenario: each parameter is independently swung to a published "low"
and "high" value, the financial kernel is re-run, and the swing in the
output metric (NPV by default, payback as an option) is recorded. The
rows are then sorted by absolute swing magnitude — the bar chart that
results is the *tornado* the thesis methodology section will cite.

OAT is a deliberate methodological choice over global (Sobol /
variance-decomposition) sensitivity:

* OAT bars are interpretable by a non-technical homeowner — "tariff
  uncertainty changes my NPV by ±X EGP" is a sentence anyone reads in
  one pass. Sobol indices are not.
* The Day-9 Monte Carlo engine already produces a *global*
  uncertainty band; the tornado is the complementary *attribution*
  view, factor by factor, that the Monte Carlo's marginalised output
  cannot give.
* OAT is the standard sensitivity reporting format in the rooftop-PV
  pre-feasibility literature (NREL SAM technical reports, IEA-PVPS
  Task 7), so the chart is directly comparable to published studies.

Every parameter exposes both an explicit ``low``/``high`` override and
falls back to a literature-anchored default range, so the tornado can
be reproduced from a single API call without the caller having to
restate the priors.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


SensitivityMetric = Literal["npv_egp", "discounted_payback_years"]

ParameterName = Literal[
    "annual_kwh",
    "tariff_egp_per_kwh",
    "cost_egp_per_kw",
    "discount_rate",
    "tariff_inflation_rate",
    "annual_degradation_rate",
    "om_cost_fraction",
]


class SensitivityRange(BaseModel):
    """Explicit low / high override for one parameter's swing range.

    When the request omits a range for a parameter, the service falls
    back to the literature-anchored default range built from the same
    Egypt-tuned distribution priors that the Monte Carlo engine uses.
    Symmetric ± fractional ranges are not exposed: every parameter has
    a published low/high pair (typically the 10th / 90th percentile
    of its Monte Carlo distribution), and forcing the caller to think
    in absolute terms keeps the tornado comparable across runs.
    """

    low: float = Field(..., description="Low end of the swing range for this parameter.")
    high: float = Field(..., description="High end of the swing range for this parameter.")

    @model_validator(mode="after")
    def _validate_low_le_high(self) -> "SensitivityRange":
        if self.low > self.high:
            raise ValueError("sensitivity range requires low <= high")
        return self


class SensitivityRequest(BaseModel):
    """Inputs for ``POST /api/sensitivity/tornado``.

    The deterministic core (system size, year-1 generation, base
    tariff) is required and is the *baseline* point at which the
    central NPV / payback figure is computed. Every other economic
    knob is optional and falls back to the configured Egypt-tuned
    defaults the way :class:`app.schemas.financial.FinancialBasicRequest`
    does, so the shape stays interchangeable across the dashboard's
    financial endpoints.

    The optional ``ranges`` mapping lets a methodology-aware caller
    override any parameter's swing range. Parameters left out of
    ``ranges`` use the literature-anchored defaults the service builds
    from the Monte Carlo prior settings.
    """

    system_kw: float = Field(..., gt=0, description="Nameplate DC capacity in kW.")
    annual_kwh: float = Field(
        ...,
        gt=0,
        description=(
            "Year-1 AC energy delivered (kWh). Consumed from either "
            "/api/energy/pvlib or /api/energy/manual."
        ),
    )
    tariff_egp_per_kwh: float = Field(
        ...,
        gt=0,
        description=(
            "Year-1 effective tariff in EGP/kWh. Tier-aware callers "
            "should pass the household's average effective rate from "
            "``/api/tariff/savings``."
        ),
    )

    cost_egp_per_kw: float | None = Field(
        None, gt=0, description="Installed cost (default: configured Egypt 2024 value)."
    )
    analysis_period_years: int | None = Field(
        None, ge=1, le=50, description="Analysis horizon (default: configured 25 years)."
    )
    discount_rate: float | None = Field(
        None, ge=0, lt=1, description="Real discount rate (default: configured 0.04)."
    )
    tariff_inflation_rate: float | None = Field(
        None,
        ge=0,
        lt=1,
        description="Annual tariff escalation (default: configured 0.08).",
    )
    annual_degradation_rate: float | None = Field(
        None,
        ge=0,
        lt=1,
        description="Per-year degradation (default: configured 0.005).",
    )
    om_cost_fraction: float | None = Field(
        None, ge=0, lt=1, description="O&M as fraction of capex (default: configured 0.01)."
    )

    metric: SensitivityMetric = Field(
        "npv_egp",
        description=(
            "Output metric whose swing the tornado measures. ``npv_egp`` "
            "is the default because NPV is always defined; "
            "``discounted_payback_years`` may be ``None`` for swings that "
            "fall outside the analysis horizon, and those rows are "
            "flagged via ``no_payback_at_low`` / ``no_payback_at_high``."
        ),
    )

    ranges: dict[ParameterName, SensitivityRange] | None = Field(
        None,
        description=(
            "Optional per-parameter override of the swing range. "
            "Parameters not listed here fall back to the configured "
            "literature-anchored ranges."
        ),
    )

    parameters: list[ParameterName] | None = Field(
        None,
        description=(
            "Optional subset of parameters to include in the tornado. "
            "Defaults to all seven supported parameters."
        ),
    )


class TornadoRow(BaseModel):
    """One bar of the tornado chart — one parameter's swing.

    ``swing`` is the absolute distance between the low and high metric
    values; the chart sorts rows by ``swing`` descending so the most
    influential parameter sits at the top, which is the convention in
    the energy-finance OAT literature. The signed deltas are also
    surfaced so the dashboard can tell the reader whether *raising* the
    parameter raises or lowers the metric — this is non-trivial since
    e.g. raising the discount rate *lowers* NPV.
    """

    parameter: ParameterName = Field(..., description="Identifier of the parameter being swung.")
    label: str = Field(
        ...,
        description=(
            "Display label for the dashboard chart. Plain English, with "
            "units."
        ),
    )
    baseline_value: float = Field(
        ..., description="The parameter's value at the deterministic baseline."
    )
    low_value: float = Field(..., description="Low end of the swing range.")
    high_value: float = Field(..., description="High end of the swing range.")
    metric_at_low: float | None = Field(
        ...,
        description=(
            "Output metric when the parameter is set to its low value. "
            "``None`` only when the metric is payback and the project "
            "fails to recover within the horizon at this low value."
        ),
    )
    metric_at_high: float | None = Field(
        ...,
        description=(
            "Output metric when the parameter is set to its high value. "
            "Same null semantics as ``metric_at_low``."
        ),
    )
    delta_low: float | None = Field(
        ...,
        description=(
            "Signed change ``metric_at_low − metric_at_baseline``. "
            "``None`` when ``metric_at_low`` is ``None``."
        ),
    )
    delta_high: float | None = Field(
        ...,
        description=(
            "Signed change ``metric_at_high − metric_at_baseline``. "
            "``None`` when ``metric_at_high`` is ``None``."
        ),
    )
    swing: float | None = Field(
        ...,
        description=(
            "Absolute distance ``|metric_at_high − metric_at_low|``. "
            "``None`` when either side could not be evaluated; the chart "
            "sorts such rows last."
        ),
    )
    no_payback_at_low: bool = Field(
        False,
        description=(
            "Set when the metric is payback and the project fails to "
            "recover at the parameter's low end."
        ),
    )
    no_payback_at_high: bool = Field(
        False,
        description=(
            "Set when the metric is payback and the project fails to "
            "recover at the parameter's high end."
        ),
    )


class SensitivityResult(BaseModel):
    """Output of ``POST /api/sensitivity/tornado``."""

    metric: SensitivityMetric = Field(..., description="Metric the tornado measures.")
    metric_at_baseline: float | None = Field(
        ...,
        description=(
            "Baseline metric value (``None`` only if metric is payback "
            "and the baseline scenario itself does not pay back, in "
            "which case the deltas are computed against the analysis "
            "horizon as a sentinel)."
        ),
    )
    rows: list[TornadoRow] = Field(
        ...,
        description=(
            "Per-parameter swing rows, sorted by ``swing`` descending. "
            "Rows where ``swing`` could not be computed sort last."
        ),
    )
    baseline_no_payback: bool = Field(
        False,
        description=(
            "Set when the metric is payback and the baseline scenario "
            "fails to recover within the analysis horizon."
        ),
    )

    # Echoed deterministic core
    system_kw: float
    annual_kwh: float
    tariff_egp_per_kwh: float
    cost_egp_per_kw: float
    analysis_period_years: int
    discount_rate: float
    tariff_inflation_rate: float
    annual_degradation_rate: float
    om_cost_fraction: float
