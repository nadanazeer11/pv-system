"""Schemas for the EgyptERA tiered-tariff service.

Day 8 introduces Contribution B of the thesis: a tariff model that takes
Egypt's *progressive marginal block* structure seriously. Three endpoints
sit on top of the same kernel —

* ``/api/tariff/bill``       compute a household's monthly and annual
                              bill from a 12-month consumption profile.
* ``/api/tariff/savings``    compute the bill, the bill *with* PV
                              generation netted off month by month, and
                              therefore the tier-aware savings.
* ``/api/tariff/optimize``   sweep a grid of system sizes and return the
                              size that maximises lifetime NPV under the
                              tiered structure.

The schemas below are the contract for those three endpoints. The tier
schedule itself is *not* part of the request payload by default — the
caller hits the EgyptERA tiers configured in ``settings`` — but every
field is overridable so the same code can score reform scenarios or
synthetic schedules used by the test suite.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TariffTier(BaseModel):
    """One block of a progressive marginal tariff schedule.

    ``upper_kwh_per_month`` is the inclusive upper bound of the band
    expressed in monthly kWh. The final band is unbounded; pass a
    positive value greater than any realistic monthly consumption (e.g.
    ``1e9``) to represent the "and above" tail. Using a finite sentinel
    rather than ``inf`` keeps the schema JSON-serialisable without
    custom encoders.

    ``egp_per_kwh`` is the marginal price applied to kWh that fall
    inside this band only. Lower bands are still charged at their own
    rates for the kWh they cover.
    """

    upper_kwh_per_month: float = Field(
        ...,
        gt=0,
        description=(
            "Inclusive upper bound of this band in kWh per month. The "
            "final band represents 'and above' — pass a sentinel like "
            "1e9 rather than infinity so the schema stays JSON-safe."
        ),
    )
    egp_per_kwh: float = Field(
        ...,
        ge=0,
        description="Marginal price (EGP/kWh) applied to consumption inside this band.",
    )


class MonthlyBillBreakdown(BaseModel):
    """One month's bill, with the per-tier decomposition kept visible.

    Exposing ``per_tier_kwh`` is what makes the Day 17 dashboard's
    "tier-bracket before vs after" chart possible without re-running the
    kernel client-side.
    """

    month_index: int = Field(..., ge=1, le=12, description="1 = January, … 12 = December.")
    consumption_kwh: float = Field(..., ge=0, description="kWh billed in this month.")
    bill_egp: float = Field(..., ge=0, description="Total EGP charged for this month.")
    per_tier_kwh: list[float] = Field(
        ...,
        description=(
            "kWh consumed inside each tier this month, in tier order. "
            "Sum equals ``consumption_kwh``."
        ),
    )
    per_tier_egp: list[float] = Field(
        ...,
        description=(
            "EGP charged inside each tier this month, in tier order. "
            "Sum equals ``bill_egp``."
        ),
    )
    marginal_tariff_egp_per_kwh: float = Field(
        ...,
        ge=0,
        description=(
            "Price of the highest tier this month's consumption reaches "
            "— the rate at which the next kWh of generation displaces "
            "consumption."
        ),
    )


# ─────────────────────────── Bill calculation ──────────────────────────


class TariffBillRequest(BaseModel):
    """Inputs for ``POST /api/tariff/bill``.

    The 12-month consumption profile is required. The schedule is
    optional — by default the EgyptERA tiers configured server-side are
    used, but a caller (or a reform-scenario unit test) can override
    them.
    """

    monthly_consumption_kwh: list[float] = Field(
        ...,
        description=(
            "Twelve consecutive monthly consumption figures in kWh, "
            "January through December."
        ),
    )
    tiers: list[TariffTier] | None = Field(
        None,
        description=(
            "Optional override of the tariff schedule. When omitted the "
            "configured EgyptERA residential tiers are used."
        ),
    )

    @field_validator("monthly_consumption_kwh")
    @classmethod
    def _twelve_months(cls, value: list[float]) -> list[float]:
        """Reject anything other than a full 12-month profile.

        Annual financial metrics (lifetime savings, payback, NPV) are
        only meaningful when one full seasonal cycle is supplied. Half-
        years would silently bias both the optimizer and the Monte
        Carlo wrapper coming in Day 9.
        """
        if len(value) != 12:
            raise ValueError("monthly_consumption_kwh must contain exactly 12 entries")
        if any(v < 0 for v in value):
            raise ValueError("monthly_consumption_kwh entries must be non-negative")
        return value

    @field_validator("tiers")
    @classmethod
    def _tiers_strictly_increasing(
        cls, value: list[TariffTier] | None
    ) -> list[TariffTier] | None:
        """Tier upper bounds must form a strictly ascending sequence.

        A non-monotonic schedule would make the per-tier decomposition
        ambiguous — two bands could claim the same kWh — and the
        marginal-rate notion would lose meaning.
        """
        if value is None:
            return None
        if len(value) == 0:
            raise ValueError("tiers must contain at least one band")
        previous = -1.0
        for tier in value:
            if tier.upper_kwh_per_month <= previous:
                raise ValueError("tier upper bounds must be strictly increasing")
            previous = tier.upper_kwh_per_month
        return value


class TariffBillResult(BaseModel):
    """Output of ``POST /api/tariff/bill``."""

    annual_bill_egp: float = Field(..., ge=0, description="Sum of the twelve monthly bills.")
    annual_consumption_kwh: float = Field(
        ..., ge=0, description="Sum of the twelve monthly consumption figures."
    )
    average_tariff_egp_per_kwh: float = Field(
        ...,
        ge=0,
        description=(
            "Annual bill ÷ annual consumption — the *effective* flat "
            "tariff a naive comparison would assume."
        ),
    )
    monthly_breakdown: list[MonthlyBillBreakdown] = Field(
        ..., description="Twelve monthly entries with the per-tier decomposition."
    )
    tiers: list[TariffTier] = Field(
        ..., description="The tier schedule actually used in the calculation (echoed)."
    )


# ───────────────────────── Savings under PV ─────────────────────────────


class TariffSavingsRequest(BaseModel):
    """Inputs for ``POST /api/tariff/savings``.

    The caller provides the household's monthly consumption *and* the
    PV system's monthly generation profile. The kernel nets the two,
    bills both the original and the netted profile, and reports the
    delta in tier-aware terms.
    """

    monthly_consumption_kwh: list[float] = Field(
        ..., description="Twelve monthly household consumption figures (kWh)."
    )
    monthly_generation_kwh: list[float] = Field(
        ...,
        description=(
            "Twelve monthly PV generation figures (kWh). Generation that "
            "exceeds month consumption is treated as zero credit "
            "(self-consumption only) — Egypt's residential net-metering "
            "scheme caps export credit at the lowest tier rate, which is "
            "modelled explicitly via ``export_credit_egp_per_kwh``."
        ),
    )
    export_credit_egp_per_kwh: float | None = Field(
        None,
        ge=0,
        description=(
            "Per-kWh credit applied to *excess* generation (generation "
            "above month consumption). When omitted, surplus generation "
            "earns zero — the conservative default that PLAN.md cites "
            "for residential rooftops in Egypt under current rules."
        ),
    )
    tiers: list[TariffTier] | None = Field(
        None, description="Optional tariff schedule override."
    )

    @field_validator("monthly_consumption_kwh", "monthly_generation_kwh")
    @classmethod
    def _twelve_months(cls, value: list[float]) -> list[float]:
        if len(value) != 12:
            raise ValueError("monthly profile must contain exactly 12 entries")
        if any(v < 0 for v in value):
            raise ValueError("monthly profile entries must be non-negative")
        return value


class TariffSavingsResult(BaseModel):
    """Output of ``POST /api/tariff/savings``."""

    bill_before_egp: float = Field(..., ge=0, description="Annual bill without PV.")
    bill_after_egp: float = Field(
        ..., ge=0, description="Annual bill with PV self-consumption applied."
    )
    annual_savings_egp: float = Field(
        ...,
        description=(
            "Bill before − bill after + export credit. Can in principle "
            "exceed the original bill if export credits are allowed."
        ),
    )
    self_consumed_kwh: float = Field(
        ..., ge=0, description="Annual kWh of generation consumed on-site."
    )
    exported_kwh: float = Field(
        ..., ge=0, description="Annual kWh of generation exceeding monthly consumption."
    )
    export_credit_egp: float = Field(
        ..., ge=0, description="Total EGP credit earned from exported energy."
    )
    average_savings_egp_per_kwh: float = Field(
        ...,
        ge=0,
        description=(
            "Annual savings ÷ annual generation. Compared with the "
            "household's average tariff, the gap quantifies the value "
            "of saving from the *top* tier first."
        ),
    )
    monthly_bill_before: list[MonthlyBillBreakdown]
    monthly_bill_after: list[MonthlyBillBreakdown]


# ────────────────────────────── Optimizer ───────────────────────────────


class TariffOptimizeRequest(BaseModel):
    """Inputs for ``POST /api/tariff/optimize``.

    The optimizer treats annual generation as scaling linearly with
    system size — doubling kW doubles annual kWh. The shape of the
    monthly profile (i.e. when the kWh arrive within the year) is held
    fixed at ``baseline_monthly_generation_kwh`` and rescaled for each
    candidate size.
    """

    monthly_consumption_kwh: list[float] = Field(
        ..., description="Household's twelve-month consumption profile (kWh)."
    )
    baseline_monthly_generation_kwh: list[float] = Field(
        ...,
        description=(
            "Twelve-month generation profile produced by the energy "
            "model for a *reference* system size. The optimizer rescales "
            "this profile linearly for each candidate kW under test."
        ),
    )
    baseline_system_kw: float = Field(
        ...,
        gt=0,
        description=(
            "Nameplate DC capacity (kW) that produced "
            "``baseline_monthly_generation_kwh``."
        ),
    )
    max_system_kw: float = Field(
        ...,
        gt=0,
        description=(
            "Upper bound of the size search (e.g. the value returned by "
            "``/api/sizing``). The optimizer never recommends a system "
            "larger than the roof can hold."
        ),
    )
    grid_step_kw: float = Field(
        0.5,
        gt=0,
        description=(
            "Granularity of the size sweep in kW. 0.5 kW corresponds to "
            "roughly one residential panel — finer than residential "
            "installers actually quote, so any optimum is sub-panel "
            "accurate."
        ),
    )
    cost_egp_per_kw: float | None = Field(
        None,
        gt=0,
        description="Installed cost per kW (default: configured Egypt market value).",
    )
    analysis_period_years: int | None = Field(None, ge=1, le=50)
    discount_rate: float | None = Field(None, ge=0, lt=1)
    tariff_inflation_rate: float | None = Field(None, ge=0, lt=1)
    annual_degradation_rate: float | None = Field(None, ge=0, lt=1)
    om_cost_fraction: float | None = Field(None, ge=0, lt=1)
    export_credit_egp_per_kwh: float | None = Field(None, ge=0)
    tiers: list[TariffTier] | None = Field(None)

    @field_validator("monthly_consumption_kwh", "baseline_monthly_generation_kwh")
    @classmethod
    def _twelve_months(cls, value: list[float]) -> list[float]:
        if len(value) != 12:
            raise ValueError("monthly profile must contain exactly 12 entries")
        if any(v < 0 for v in value):
            raise ValueError("monthly profile entries must be non-negative")
        return value


class OptimizationCandidate(BaseModel):
    """One point on the size-vs-NPV sweep curve."""

    system_kw: float = Field(..., ge=0)
    annual_generation_kwh: float = Field(..., ge=0)
    year1_savings_egp: float = Field(...)
    capex_egp: float = Field(..., ge=0)
    npv_egp: float = Field(...)
    simple_payback_years: float | None = Field(None)
    discounted_payback_years: float | None = Field(None)


class TariffOptimizeResult(BaseModel):
    """Output of ``POST /api/tariff/optimize``."""

    optimal_system_kw: float = Field(
        ..., ge=0, description="System size that maximises NPV under the tiered schedule."
    )
    optimal_npv_egp: float = Field(...)
    optimal_year1_savings_egp: float = Field(...)
    optimal_simple_payback_years: float | None = Field(None)
    optimal_discounted_payback_years: float | None = Field(None)
    flat_tariff_optimum_kw: float = Field(
        ...,
        ge=0,
        description=(
            "Optimum that a *flat-tariff* model would have recommended — "
            "the value of the household's average tariff applied to every "
            "saved kWh. Reporting both makes Contribution B's effect "
            "visible: tier-aware optimisation typically recommends a "
            "smaller system than flat-tariff optimisation, because "
            "marginal savings drop sharply once consumption is pulled "
            "down into the cheap tiers."
        ),
    )
    candidates: list[OptimizationCandidate] = Field(
        ..., description="Full size-vs-NPV sweep so the frontend can plot the curve."
    )
    tiers: list[TariffTier]
    analysis_period_years: int
    discount_rate: float
    tariff_inflation_rate: float
    annual_degradation_rate: float
    om_cost_fraction: float
    cost_egp_per_kw: float
    export_credit_egp_per_kwh: float
