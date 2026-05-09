"""Schemas for load-profile-driven PV sizing.

The standard `/api/sizing` flow goes *area → system kW*. This module
inverts the question: given an appliance load profile, what system kW
is needed to cover it, and does the available roof have enough area?

Homeowners rarely know their exact monthly kWh consumption but can
list the appliances they own — the appliance library on the service
side turns that list into a daily-load figure that drives the
recommendation.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ApplianceEntry(BaseModel):
    """One line of the user's appliance load profile.

    `watts` is the appliance's continuous draw under typical use, not
    its peak inrush — the load model multiplies by hours-per-day to get
    energy, so a momentary kettle spike is irrelevant. `hours_per_day`
    is the *daily-averaged* usage so weekly / seasonal patterns can be
    smoothed in the UI without changing the backend contract.
    """

    name: str = Field(..., min_length=1, max_length=80, description="Human label, e.g. 'Air conditioner'")
    watts: float = Field(..., gt=0, le=10000, description="Average continuous draw in watts")
    hours_per_day: float = Field(..., ge=0, le=24, description="Average usage hours per day")
    quantity: int = Field(1, ge=1, le=100, description="How many of this appliance the household runs")


class LoadSizingRequest(BaseModel):
    """Inputs for the load-driven sizing calculation."""

    appliances: list[ApplianceEntry] = Field(..., min_length=1, description="Appliance load profile")
    available_roof_area_m2: float | None = Field(
        None,
        gt=0,
        description=(
            "Optional. If supplied the response includes a roof-fit check that "
            "reports whether the recommended system physically fits."
        ),
    )
    coverage_fraction: float = Field(
        1.0,
        gt=0,
        le=1,
        description=(
            "Fraction of the daily load the PV system should aim to cover. "
            "1.0 = full offset; 0.5 = size for half the load."
        ),
    )
    panel_rated_watts: float | None = Field(None, gt=0)
    panel_area_m2: float | None = Field(None, gt=0)
    roof_utilization_factor: float | None = Field(None, gt=0, le=1)


class ApplianceLibraryEntry(BaseModel):
    """One pre-seeded appliance the UI can offer as a starting point."""

    name: str
    watts: float
    typical_hours_per_day: float
    category: str


class LoadSizingResult(BaseModel):
    """Recommendation derived from the appliance load profile."""

    daily_load_kwh: float = Field(..., description="Total daily energy demand from the appliance list")
    monthly_load_kwh: float = Field(..., description="Daily load × 30.4 (average month)")
    annual_load_kwh: float = Field(..., description="Daily load × 365")
    peak_load_kw: float = Field(..., description="Sum of (watts × quantity) — worst-case simultaneous draw")

    recommended_system_kw: float = Field(..., description="DC nameplate capacity to cover coverage_fraction of daily load")
    recommended_panel_count: int = Field(..., ge=0)
    required_roof_area_m2: float = Field(..., description="Total roof area needed (gross, after applying utilization factor)")

    coverage_fraction: float
    peak_sun_hours: float
    performance_ratio: float

    panel_rated_watts: float
    panel_area_m2: float
    roof_utilization_factor: float

    roof_fits: bool | None = Field(
        None,
        description=(
            "True if available_roof_area_m2 >= required_roof_area_m2. "
            "Null when no roof area was supplied."
        ),
    )
    available_roof_area_m2: float | None = None
    roof_area_shortfall_m2: float | None = Field(
        None,
        description="required_roof_area_m2 - available_roof_area_m2 when the roof is too small",
    )
