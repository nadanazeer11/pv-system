"""Schemas for the CO₂ avoidance service.

Day 18 introduces the environmental-benefit half of the dashboard's
"why does this matter beyond money?" story. The service translates a
year-1 generation figure into a *lifetime* CO₂-avoided quantity using
the published Egyptian grid emission factor (EEHC, 2023), and into
three EPA-published "equivalences" (passenger-car kilometres avoided,
petrol litres avoided, urban-tree-years of sequestration matched) so
the headline number is a quantity a homeowner can picture rather than
an opaque tonne-of-CO₂ figure.

The contract mirrors the basic financial schema's design philosophy:
every assumption used in the calculation is echoed back in the
response so the JSON itself is a self-auditing artefact a thesis
reviewer can re-check without consulting either server config or the
request body.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CO2Request(BaseModel):
    """Inputs for ``POST /api/co2/avoided``.

    Only the year-1 generation figure is required; every economic /
    environmental knob has an Egypt-tuned default in
    :pydata:`app.config.settings`. Holding the schema parallel to
    :class:`app.schemas.financial.FinancialBasicRequest` for the
    parameters they share (analysis horizon, degradation rate) means
    the dashboard can pass the same payload shape to both endpoints
    with a single field rename.
    """

    annual_kwh: float = Field(
        ...,
        gt=0,
        description=(
            "Year-1 AC energy delivered (kWh). Consume the value from "
            "either /api/energy/pvlib or /api/energy/manual."
        ),
    )
    analysis_period_years: int | None = Field(
        None,
        ge=1,
        le=50,
        description=(
            "Analysis horizon in years (default: configured 25-year "
            "module performance warranty term)."
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
    grid_emission_factor_kg_per_kwh: float | None = Field(
        None,
        ge=0,
        description=(
            "Marginal grid emission factor (kg CO₂ per kWh of grid "
            "electricity displaced). Default: configured 0.46 kg/kWh "
            "(EEHC 2023 for the Egyptian grid)."
        ),
    )


class CO2YearlyPoint(BaseModel):
    """One year of the year-by-year CO₂ avoidance trajectory."""

    year: int = Field(..., ge=1, description="1-based year index from system commissioning.")
    generation_kwh: float = Field(
        ...,
        ge=0,
        description="Degraded annual generation in this year (kWh).",
    )
    co2_avoided_kg: float = Field(
        ...,
        ge=0,
        description=(
            "CO₂ avoided in this year (kg) = generation × emission factor."
        ),
    )


class CO2Equivalents(BaseModel):
    """Homeowner-friendly equivalences for the lifetime CO₂ figure.

    The three units below come from the US EPA Greenhouse Gas
    Equivalencies Calculator's published reference values and are the
    standard set used in consumer-facing climate communication. They
    are deliberately not summed with each other — each is an
    independent translation of the *same* lifetime kg-CO₂ total into a
    different mental model.
    """

    equivalent_passenger_car_km: float = Field(
        ...,
        ge=0,
        description=(
            "Kilometres of average passenger-car driving that would emit "
            "the same lifetime CO₂ as this system avoids."
        ),
    )
    equivalent_petrol_litres: float = Field(
        ...,
        ge=0,
        description=(
            "Litres of petrol whose combustion would emit the same "
            "lifetime CO₂ as this system avoids."
        ),
    )
    equivalent_urban_trees_grown: float = Field(
        ...,
        ge=0,
        description=(
            "Number of urban trees that would sequester the same CO₂ "
            "over the analysis horizon (10-year-average per-tree "
            "sequestration rate)."
        ),
    )


class CO2Result(BaseModel):
    """Output of ``POST /api/co2/avoided``.

    ``cumulative_co2_avoided_kg`` is one entry longer than
    ``annual_series``: index 0 is the year-of-commissioning baseline
    (zero), index ``k`` is the cumulative kg-CO₂ avoided through the
    end of year ``k``. The Day-18 dashboard tornado/comparison view
    reads the cumulative trajectory directly to draw the running
    "carbon savings" curve without re-running the kernel.
    """

    annual_co2_avoided_year1_kg: float = Field(
        ...,
        ge=0,
        description=(
            "First-year CO₂ avoided (kg) = year-1 generation × emission "
            "factor."
        ),
    )
    lifetime_co2_avoided_kg: float = Field(
        ..., ge=0, description="Sum of degraded annual CO₂ avoided over the analysis period."
    )
    lifetime_co2_avoided_tonnes: float = Field(
        ...,
        ge=0,
        description=(
            "Same total as ``lifetime_co2_avoided_kg`` but in metric "
            "tonnes — the headline unit on the dashboard's CO₂ card."
        ),
    )
    annual_series: list[CO2YearlyPoint] = Field(
        ...,
        description=(
            "Year-by-year CO₂ avoidance points (length = "
            "analysis_period_years)."
        ),
    )
    cumulative_co2_avoided_kg: list[float] = Field(
        ...,
        description=(
            "Cumulative CO₂ avoided through the end of each year, "
            "starting at 0 in year 0 (length = analysis_period_years + 1)."
        ),
    )
    equivalents: CO2Equivalents = Field(
        ...,
        description=(
            "Homeowner-friendly translations of the lifetime CO₂ figure."
        ),
    )

    # Echoed assumptions
    annual_kwh: float
    analysis_period_years: int
    annual_degradation_rate: float
    grid_emission_factor_kg_per_kwh: float
