"""Schemas for the Monte Carlo uncertainty engine.

Day 9 introduces Contribution C of the thesis: a stochastic wrapper
around the financial kernel that treats the parameters with the largest
real-world uncertainty (degradation, tariff escalation, capex, O&M,
weather/soiling year-to-year, inverter replacement cost and timing) as
*probability distributions* rather than point estimates.

A single run draws ``n_simulations`` independent samples for each
distribution, evaluates the same year-by-year cash-flow model that the
deterministic ``financial_basic`` service uses, and reports

* the *distribution* of payback years, NPV, LCOE and lifetime savings
  (mean, standard deviation, 5/10/25/50/75/90/95 percentiles),
* the *probability* that the project pays back within the analysis
  horizon and that NPV is positive,
* histogram bins for payback and NPV so the dashboard can plot the
  shape of the distributions without re-running the kernel.

The contract intentionally exposes every distribution as an *override*
rather than baking the Egypt-tuned defaults into the request payload.
A caller can therefore reproduce any published deterministic figure by
collapsing every distribution to zero variance, and the test suite
exploits that to pin down the kernel's behaviour with closed-form
expectations.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


DistributionKind = Literal["normal", "triangular"]


class Distribution(BaseModel):
    """Parametric distribution used to sample one uncertain input.

    Two families are supported — they cover the academically relevant
    cases without forcing the API surface to grow as new parameters are
    added:

    * ``normal`` — symmetric, characterised by ``mean`` and ``std``. The
      natural choice when published uncertainty is reported as a ±σ
      interval (e.g. tariff inflation 8 % ± 3 %).
    * ``triangular`` — bounded, characterised by ``low``, ``mode``,
      ``high``. The natural choice for parameters with hard physical
      bounds and a published "best estimate" point (e.g. NREL panel
      degradation: 0.2–1.0 %/yr, ~0.5 %/yr typical).

    ``clip_min`` / ``clip_max`` are applied *after* sampling. They make
    a normal distribution physically defensible when the parameter has
    a hard floor (e.g. degradation must be ≥ 0).
    """

    kind: DistributionKind = Field(..., description="Distribution family.")
    mean: float | None = Field(
        None, description="Mean of the normal distribution. Required when kind='normal'."
    )
    std: float | None = Field(
        None,
        ge=0,
        description=(
            "Standard deviation of the normal distribution. Required when "
            "kind='normal'. Setting std=0 collapses to a deterministic "
            "constant equal to ``mean`` — useful for unit tests."
        ),
    )
    low: float | None = Field(
        None,
        description="Lower bound of the triangular distribution. Required when kind='triangular'.",
    )
    mode: float | None = Field(
        None,
        description="Most-likely value of the triangular distribution. Required when kind='triangular'.",
    )
    high: float | None = Field(
        None,
        description="Upper bound of the triangular distribution. Required when kind='triangular'.",
    )
    clip_min: float | None = Field(
        None,
        description=(
            "Optional hard floor applied after sampling (e.g. 0 to "
            "prevent negative degradation rates from a normal draw)."
        ),
    )
    clip_max: float | None = Field(
        None, description="Optional hard ceiling applied after sampling."
    )

    @model_validator(mode="after")
    def _validate_kind_specific_fields(self) -> "Distribution":
        """Reject under-specified or inconsistent distribution payloads."""
        if self.kind == "normal":
            if self.mean is None or self.std is None:
                raise ValueError("normal distribution requires 'mean' and 'std'")
        elif self.kind == "triangular":
            if self.low is None or self.mode is None or self.high is None:
                raise ValueError(
                    "triangular distribution requires 'low', 'mode' and 'high'"
                )
            if not (self.low <= self.mode <= self.high):
                raise ValueError("triangular requires low <= mode <= high")
            # ``low == high`` is permitted on purpose: it collapses the
            # distribution to a deterministic constant, which is the
            # idiomatic way for callers (and the test suite) to disable
            # one source of uncertainty without having to switch to a
            # zero-σ normal. The sampler handles the zero-width case.
        if (
            self.clip_min is not None
            and self.clip_max is not None
            and self.clip_min > self.clip_max
        ):
            raise ValueError("clip_min must not exceed clip_max")
        return self


class MonteCarloRequest(BaseModel):
    """Inputs for ``POST /api/monte-carlo/run``.

    The deterministic core (system size, year-1 generation, base tariff,
    analysis period, discount rate) is required; every uncertain
    parameter has a server-side default distribution which the caller
    may override. Defaults are tuned to Egypt residential rooftop PV
    (PLAN.md §"Egypt-Specific Assumptions").
    """

    system_kw: float = Field(..., gt=0, description="Nameplate DC capacity in kW.")
    annual_kwh: float = Field(
        ...,
        gt=0,
        description=(
            "Year-1 AC energy delivered (kWh) under nominal weather. "
            "Year-to-year weather and soiling variability is sampled via "
            "``annual_yield_factor_dist``."
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

    analysis_period_years: int | None = Field(
        None,
        ge=1,
        le=50,
        description="Analysis horizon (default: configured 25-year warranty).",
    )
    discount_rate: float | None = Field(
        None, ge=0, lt=1, description="Real discount rate, fraction (default: configured)."
    )

    n_simulations: int = Field(
        1000,
        ge=10,
        le=20000,
        description=(
            "Number of independent Monte Carlo draws. PLAN.md target is "
            "1 000 — sufficient for ±0.05-year confidence on payback "
            "median by Hoeffding's inequality at the observed σ."
        ),
    )
    random_seed: int | None = Field(
        None,
        description=(
            "Optional seed for the underlying NumPy generator. When set, "
            "the same request returns byte-identical output — critical "
            "for the deterministic test suite."
        ),
    )

    degradation_rate_dist: Distribution | None = Field(
        None,
        description=(
            "Distribution for the per-year fractional output drop. "
            "Default: triangular(0.002, 0.005, 0.010) — NREL bounds for "
            "mono-Si under standard warranty terms."
        ),
    )
    tariff_inflation_rate_dist: Distribution | None = Field(
        None,
        description=(
            "Distribution for the annual tariff escalation rate. "
            "Default: normal(0.08, 0.03), clipped at zero — matches the "
            "EgyptERA decade trend cited in PLAN.md."
        ),
    )
    om_cost_fraction_dist: Distribution | None = Field(
        None,
        description=(
            "Distribution for annual O&M as a fraction of capex. "
            "Default: triangular(0.005, 0.010, 0.020) — IRENA residential "
            "rooftop benchmark range."
        ),
    )
    cost_egp_per_kw_dist: Distribution | None = Field(
        None,
        description=(
            "Distribution for installed cost (EGP/kW). Default: "
            "triangular(30 000, 35 000, 45 000) — Egyptian market 2024 "
            "spread reflecting installer-to-installer quote variance."
        ),
    )
    annual_yield_factor_dist: Distribution | None = Field(
        None,
        description=(
            "Per-year, per-simulation multiplier on energy yield, capturing "
            "weather variability and soiling. Default: normal(1.0, 0.05), "
            "clipped at 0.5–1.5 — consistent with TMY-vs-actual residual "
            "variance reported in Egyptian PV field studies."
        ),
    )
    inverter_replacement_year_dist: Distribution | None = Field(
        None,
        description=(
            "Distribution over the year of (single) inverter replacement. "
            "Default: triangular(10, 12, 15). Sampled values are rounded "
            "to the nearest integer year and clipped into the analysis "
            "horizon."
        ),
    )
    inverter_replacement_cost_fraction_dist: Distribution | None = Field(
        None,
        description=(
            "Replacement cost as a fraction of original capex. Default: "
            "triangular(0.07, 0.10, 0.15)."
        ),
    )

    @field_validator("n_simulations")
    @classmethod
    def _power_of_some_thousand(cls, value: int) -> int:
        """No real constraint — kept as a hook for future stratification."""
        return value


class MonteCarloPercentiles(BaseModel):
    """Summary of one metric across the simulation ensemble.

    Reporting ``mean ± std`` alongside the 5–95 % percentile band makes
    the asymmetry of the simulated distribution visible: payback in
    particular is heavily right-skewed (a fat tail of "never recovers"
    runs) and a Gaussian-style ``mean ± std`` would mis-represent it on
    its own.
    """

    mean: float = Field(..., description="Sample mean across simulations.")
    std: float = Field(..., ge=0, description="Sample standard deviation.")
    p05: float = Field(..., description="5th percentile.")
    p10: float = Field(..., description="10th percentile.")
    p25: float = Field(..., description="25th percentile.")
    p50: float = Field(..., description="Median (50th percentile).")
    p75: float = Field(..., description="75th percentile.")
    p90: float = Field(..., description="90th percentile.")
    p95: float = Field(..., description="95th percentile.")
    minimum: float = Field(..., description="Minimum value observed in the ensemble.")
    maximum: float = Field(..., description="Maximum value observed in the ensemble.")


class HistogramBins(BaseModel):
    """Frequency histogram for a metric, ready for the dashboard chart."""

    bin_edges: list[float] = Field(
        ...,
        description=(
            "Histogram bin edges, length = ``len(counts) + 1``. The "
            "i-th bin spans ``[bin_edges[i], bin_edges[i+1])``."
        ),
    )
    counts: list[int] = Field(
        ..., description="Number of simulations falling in each bin."
    )


class CumulativeCashFlowTrajectory(BaseModel):
    """Year-by-year discounted cumulative cash-flow percentile bands.

    Day 16 introduces the dashboard's "fan chart for cumulative ROI":
    instead of one curve, we show how the project's running net worth
    evolves under the full ensemble of Monte Carlo simulations. Each
    array is length ``analysis_period_years + 1`` — index 0 is the
    year-0 capex draw (a negative number whose own spread reflects
    capex-quote uncertainty), and index ``k`` is the discounted
    cumulative cash flow at the end of year ``k`` aggregated *across*
    the simulation ensemble.

    Reporting bands rather than a single mean curve is the whole point
    of the contribution: a homeowner sees not just "the median crosses
    zero in year 7" but also "the worst-case 5 % of futures still owe
    money in year 12" and "the best 5 % of futures double their money
    by year 15".
    """

    year_index: list[int] = Field(
        ...,
        description=(
            "Year markers from 0 (year of capex draw) through the "
            "analysis horizon. Length = analysis_period_years + 1."
        ),
    )
    p05: list[float] = Field(..., description="5th-percentile band (EGP).")
    p25: list[float] = Field(..., description="25th-percentile band (EGP).")
    p50: list[float] = Field(..., description="Median trajectory (EGP).")
    p75: list[float] = Field(..., description="75th-percentile band (EGP).")
    p95: list[float] = Field(..., description="95th-percentile band (EGP).")
    mean: list[float] = Field(..., description="Sample-mean trajectory (EGP).")


class MonteCarloResult(BaseModel):
    """Output of ``POST /api/monte-carlo/run``."""

    n_simulations: int = Field(..., description="Number of Monte Carlo draws executed.")
    payback_years: MonteCarloPercentiles = Field(
        ...,
        description=(
            "Discounted payback year, computed by linear interpolation. "
            "Simulations that never reach break-even within the analysis "
            "horizon are excluded from these percentiles — the share of "
            "such runs is reported separately via ``payback_probability``."
        ),
    )
    npv_egp: MonteCarloPercentiles = Field(
        ..., description="Net present value distribution across simulations."
    )
    lcoe_egp_per_kwh: MonteCarloPercentiles = Field(
        ...,
        description=(
            "Levelised cost of electricity distribution. Includes the "
            "discounted inverter-replacement cost in the numerator."
        ),
    )
    lifetime_savings_egp: MonteCarloPercentiles = Field(
        ...,
        description=(
            "Sum of (un-discounted) annual savings across the analysis "
            "period."
        ),
    )

    payback_probability: float = Field(
        ...,
        ge=0,
        le=1,
        description=(
            "Fraction of simulations whose discounted cumulative cash "
            "flow turns non-negative within the analysis horizon."
        ),
    )
    positive_npv_probability: float = Field(
        ...,
        ge=0,
        le=1,
        description="Fraction of simulations with NPV > 0.",
    )

    payback_histogram: HistogramBins = Field(
        ...,
        description=(
            "Histogram of payback years (paid-back simulations only)."
        ),
    )
    npv_histogram: HistogramBins = Field(
        ..., description="Histogram of NPV across all simulations."
    )

    cumulative_cash_flow_trajectory: CumulativeCashFlowTrajectory = Field(
        ...,
        description=(
            "Year-by-year percentile bands of the discounted cumulative "
            "cash flow. Drives the Day-16 dashboard fan chart and lets a "
            "reviewer read off the median ROI year, the worst-case "
            "trough, and the best-case lifetime gain in one figure."
        ),
    )

    # Echoed deterministic inputs.
    system_kw: float
    annual_kwh: float
    tariff_egp_per_kwh: float
    analysis_period_years: int
    discount_rate: float
    random_seed: int | None
