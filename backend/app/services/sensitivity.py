"""One-at-a-time (OAT) sensitivity / tornado analysis kernel.

The Day-18 thesis deliverable answers two related-but-distinct
questions:

* "Which input matters most?" — the OAT tornado computed in this
  module.
* "How wide is the joint uncertainty?" — the Day-9 Monte Carlo
  histogram and confidence interval.

The tornado below is the *attribution* view: each parameter is
swung independently between a literature-anchored low and high while
all other parameters stay at the deterministic baseline, the
financial kernel is re-run, and the resulting metric swing is
recorded as one bar of a horizontal tornado chart sorted by absolute
swing. The dashboard renders the rows in descending order so the
parameter with the most leverage on NPV (or payback) sits at the top.

Why OAT and not Sobol / variance-decomposition?
------------------------------------------------
Sobol indices give a more complete picture of joint sensitivity but
are not directly interpretable as "this parameter changes my NPV by
±X EGP" — they are *fractional contributions to output variance* and
require a non-trivial statistical literacy to read. The OAT tornado is
the standard reporting format in the rooftop-PV pre-feasibility
literature (NREL SAM Technical Reference, IEA-PVPS Task 7) and the
format the bachelor-thesis dashboard's homeowner audience can read in
a single pass. The Day-9 Monte Carlo engine, which *does* model joint
uncertainty, is the complementary figure — together they cover both
sensitivity questions a methodology section is expected to address.

Why a deterministic re-run rather than an algebraic sensitivity?
----------------------------------------------------------------
Several of the parameters interact nonlinearly with each other through
the cash-flow chain (e.g. degradation × tariff inflation × discount
rate compounds across years). Closed-form partial derivatives would be
a wall of algebra that is harder to audit than seven reproducible
deterministic re-runs of the same kernel the deterministic dashboard
uses. The cost is one financial-kernel evaluation per parameter per
side ≈ fourteen evaluations total — a millisecond-scale cost.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.schemas.financial import FinancialBasicRequest
from app.schemas.sensitivity import (
    ParameterName,
    SensitivityMetric,
    SensitivityRange,
    SensitivityRequest,
    SensitivityResult,
    TornadoRow,
)
from app.services import financial_basic


class SensitivityError(ValueError):
    """Raised when sensitivity inputs are inconsistent with the kernel.

    Most input validation happens at the Pydantic layer; this error is
    reserved for invariants the schema cannot express, such as a
    settings reload that introduces ``low > high`` in a configured
    swing range.
    """


# Display labels for the dashboard tornado. Plain English, units-bearing.
_PARAMETER_LABELS: dict[ParameterName, str] = {
    "annual_kwh": "Annual generation (kWh/yr)",
    "tariff_egp_per_kwh": "Electricity tariff (EGP/kWh)",
    "cost_egp_per_kw": "Installed cost (EGP/kW)",
    "discount_rate": "Discount rate (%/yr)",
    "tariff_inflation_rate": "Tariff escalation (%/yr)",
    "annual_degradation_rate": "Module degradation (%/yr)",
    "om_cost_fraction": "O&M cost (% of capex)",
}


# Default ordering used when the request omits ``parameters``. This is
# also the canonical order the methodology section's tornado figure
# uses *before* the swing-magnitude sort, so a reader can cross-check
# any pre-sort version against the schema.
_DEFAULT_PARAMETERS: tuple[ParameterName, ...] = (
    "annual_kwh",
    "tariff_egp_per_kwh",
    "cost_egp_per_kw",
    "discount_rate",
    "tariff_inflation_rate",
    "annual_degradation_rate",
    "om_cost_fraction",
)


@dataclass(frozen=True)
class _ResolvedBaseline:
    """Snapshot of every financial-kernel input at the deterministic baseline."""

    system_kw: float
    annual_kwh: float
    tariff_egp_per_kwh: float
    cost_egp_per_kw: float
    analysis_period_years: int
    discount_rate: float
    tariff_inflation_rate: float
    annual_degradation_rate: float
    om_cost_fraction: float


def _resolve_baseline(request: SensitivityRequest) -> _ResolvedBaseline:
    """Materialise every kernel input at the deterministic baseline.

    The schema lets the caller leave economic knobs at ``None``, but
    the tornado service needs concrete numbers for every parameter so
    the per-parameter swing never accidentally cancels against a
    settings reload mid-evaluation. Resolving the baseline once
    upfront also lets the result echo every assumption back to the
    caller for self-auditing — the same convention as
    :func:`financial_basic.compute_financials`.
    """
    return _ResolvedBaseline(
        system_kw=request.system_kw,
        annual_kwh=request.annual_kwh,
        tariff_egp_per_kwh=request.tariff_egp_per_kwh,
        cost_egp_per_kw=(
            request.cost_egp_per_kw
            if request.cost_egp_per_kw is not None
            else settings.installed_cost_egp_per_kw
        ),
        analysis_period_years=(
            request.analysis_period_years
            if request.analysis_period_years is not None
            else settings.analysis_period_years
        ),
        discount_rate=(
            request.discount_rate
            if request.discount_rate is not None
            else settings.discount_rate
        ),
        tariff_inflation_rate=(
            request.tariff_inflation_rate
            if request.tariff_inflation_rate is not None
            else settings.tariff_inflation_rate
        ),
        annual_degradation_rate=(
            request.annual_degradation_rate
            if request.annual_degradation_rate is not None
            else settings.annual_degradation_rate
        ),
        om_cost_fraction=(
            request.om_cost_fraction
            if request.om_cost_fraction is not None
            else settings.om_cost_fraction
        ),
    )


def _default_range(
    parameter: ParameterName, baseline: _ResolvedBaseline
) -> SensitivityRange:
    """Produce the literature-anchored low/high swing range for a parameter.

    For ``annual_kwh`` and ``tariff_egp_per_kwh`` the configured range
    is a *fractional* multiplier on the baseline (since a £/kWh tariff
    or a kWh/yr yield has no model-wide reference value); for the
    remaining five parameters the configured range is the absolute
    low/high pair (e.g. ``(0.002, 0.010)`` for degradation), aligned
    with the corresponding Monte Carlo prior so the tornado and the
    Monte Carlo histogram cite the same band.
    """
    if parameter == "annual_kwh":
        lo, hi = settings.sensitivity_yield_factor_range
        return SensitivityRange(low=baseline.annual_kwh * lo, high=baseline.annual_kwh * hi)
    if parameter == "tariff_egp_per_kwh":
        lo, hi = settings.sensitivity_tariff_factor_range
        return SensitivityRange(
            low=baseline.tariff_egp_per_kwh * lo,
            high=baseline.tariff_egp_per_kwh * hi,
        )
    if parameter == "cost_egp_per_kw":
        lo, hi = settings.sensitivity_cost_egp_per_kw_range
        return SensitivityRange(low=lo, high=hi)
    if parameter == "discount_rate":
        lo, hi = settings.sensitivity_discount_rate_range
        return SensitivityRange(low=lo, high=hi)
    if parameter == "tariff_inflation_rate":
        lo, hi = settings.sensitivity_tariff_inflation_range
        return SensitivityRange(low=lo, high=hi)
    if parameter == "annual_degradation_rate":
        lo, hi = settings.sensitivity_degradation_rate_range
        return SensitivityRange(low=lo, high=hi)
    if parameter == "om_cost_fraction":
        lo, hi = settings.sensitivity_om_cost_fraction_range
        return SensitivityRange(low=lo, high=hi)
    raise SensitivityError(f"unsupported sensitivity parameter: {parameter}")


def _baseline_value(parameter: ParameterName, baseline: _ResolvedBaseline) -> float:
    """Read the parameter's value out of the resolved baseline."""
    return float(getattr(baseline, parameter))


def _build_request(
    baseline: _ResolvedBaseline, *, parameter: ParameterName, value: float
) -> FinancialBasicRequest:
    """Construct a :class:`FinancialBasicRequest` with one parameter swapped.

    The financial kernel is the single source of truth for the metric;
    the tornado service merely re-invokes it with one input swung at a
    time. Building a fresh request per evaluation keeps the kernel
    side-effect-free and makes the swing arithmetic auditable from the
    request body alone.
    """
    payload = {
        "system_kw": baseline.system_kw,
        "annual_kwh": baseline.annual_kwh,
        "tariff_egp_per_kwh": baseline.tariff_egp_per_kwh,
        "cost_egp_per_kw": baseline.cost_egp_per_kw,
        "analysis_period_years": baseline.analysis_period_years,
        "discount_rate": baseline.discount_rate,
        "tariff_inflation_rate": baseline.tariff_inflation_rate,
        "annual_degradation_rate": baseline.annual_degradation_rate,
        "om_cost_fraction": baseline.om_cost_fraction,
    }
    payload[parameter] = value
    return FinancialBasicRequest(**payload)


def _extract_metric(
    result: financial_basic.FinancialBasic, metric: SensitivityMetric
) -> float | None:
    """Pluck the requested headline figure out of a kernel result.

    Returns ``None`` for the payback metric when the project does not
    pay back within the analysis horizon — the deterministic kernel
    flags this with a ``None`` payback already, and the tornado row
    surfaces it explicitly via the ``no_payback_at_*`` booleans.
    """
    if metric == "npv_egp":
        return float(result.npv_egp)
    if metric == "discounted_payback_years":
        return None if result.discounted_payback_years is None else float(
            result.discounted_payback_years
        )
    raise SensitivityError(f"unsupported sensitivity metric: {metric}")


def _row_for_parameter(
    *,
    parameter: ParameterName,
    baseline: _ResolvedBaseline,
    range_: SensitivityRange,
    metric: SensitivityMetric,
    metric_at_baseline: float | None,
) -> TornadoRow:
    """Compute one tornado bar for one parameter."""
    baseline_value = _baseline_value(parameter, baseline)

    low_request = _build_request(baseline, parameter=parameter, value=range_.low)
    high_request = _build_request(baseline, parameter=parameter, value=range_.high)

    low_result = financial_basic.compute_financials(low_request)
    high_result = financial_basic.compute_financials(high_request)

    metric_at_low = _extract_metric(low_result, metric)
    metric_at_high = _extract_metric(high_result, metric)

    no_payback_at_low = metric == "discounted_payback_years" and metric_at_low is None
    no_payback_at_high = metric == "discounted_payback_years" and metric_at_high is None

    delta_low: float | None
    delta_high: float | None
    if metric_at_baseline is None:
        delta_low = None if metric_at_low is None else metric_at_low
        delta_high = None if metric_at_high is None else metric_at_high
    else:
        delta_low = None if metric_at_low is None else metric_at_low - metric_at_baseline
        delta_high = None if metric_at_high is None else metric_at_high - metric_at_baseline

    swing: float | None
    if metric_at_low is None or metric_at_high is None:
        swing = None
    else:
        swing = abs(metric_at_high - metric_at_low)

    return TornadoRow(
        parameter=parameter,
        label=_PARAMETER_LABELS[parameter],
        baseline_value=baseline_value,
        low_value=range_.low,
        high_value=range_.high,
        metric_at_low=metric_at_low,
        metric_at_high=metric_at_high,
        delta_low=delta_low,
        delta_high=delta_high,
        swing=swing,
        no_payback_at_low=no_payback_at_low,
        no_payback_at_high=no_payback_at_high,
    )


def run_sensitivity(request: SensitivityRequest) -> SensitivityResult:
    """Execute the OAT tornado sweep and return the sorted result.

    Parameters
    ----------
    request : SensitivityRequest
        Deterministic baseline plus optional metric / range / parameter
        overrides.

    Returns
    -------
    SensitivityResult
        One :class:`TornadoRow` per parameter, sorted by absolute swing
        descending. Rows whose swing could not be computed (the metric
        is payback and *one* side did not pay back) sort to the bottom
        of the chart.

    Raises
    ------
    SensitivityError
        Only for invariants the schema cannot express.
    """
    baseline = _resolve_baseline(request)

    parameters = (
        request.parameters
        if request.parameters is not None
        else list(_DEFAULT_PARAMETERS)
    )

    baseline_request = _build_request(
        baseline, parameter="annual_kwh", value=baseline.annual_kwh
    )
    baseline_result = financial_basic.compute_financials(baseline_request)
    metric_at_baseline = _extract_metric(baseline_result, request.metric)
    baseline_no_payback = (
        request.metric == "discounted_payback_years" and metric_at_baseline is None
    )

    overrides = request.ranges or {}
    rows: list[TornadoRow] = []
    for parameter in parameters:
        range_ = overrides.get(parameter) or _default_range(parameter, baseline)
        rows.append(
            _row_for_parameter(
                parameter=parameter,
                baseline=baseline,
                range_=range_,
                metric=request.metric,
                metric_at_baseline=metric_at_baseline,
            )
        )

    # Sort by absolute swing descending; rows with ``swing is None``
    # sort to the bottom (None is treated as the smallest possible
    # swing for ranking purposes — they convey "evaluate the
    # individual ends" rather than "this parameter has zero leverage").
    rows.sort(key=lambda r: (r.swing is None, -(r.swing or 0.0)))

    return SensitivityResult(
        metric=request.metric,
        metric_at_baseline=metric_at_baseline,
        rows=rows,
        baseline_no_payback=baseline_no_payback,
        system_kw=baseline.system_kw,
        annual_kwh=baseline.annual_kwh,
        tariff_egp_per_kwh=baseline.tariff_egp_per_kwh,
        cost_egp_per_kw=baseline.cost_egp_per_kw,
        analysis_period_years=baseline.analysis_period_years,
        discount_rate=baseline.discount_rate,
        tariff_inflation_rate=baseline.tariff_inflation_rate,
        annual_degradation_rate=baseline.annual_degradation_rate,
        om_cost_fraction=baseline.om_cost_fraction,
    )
