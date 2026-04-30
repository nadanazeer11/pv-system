"""Schemas for the energy estimation endpoints.

The response intentionally echoes orientation, losses, and key
performance metrics so the JSON itself is self-auditing — a thesis
reviewer can verify the assumptions without consulting server config.

Two parallel families of request/result schemas exist — one for the
pvlib (industry-standard) chain and one for the manual physics chain —
so the two halves of the dual-energy backbone can be exposed
side-by-side in the OpenAPI docs without one masquerading as the other.
The shapes are intentionally identical: cross-validation in the
upcoming comparison view is a one-line diff.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.inputs import Location


class EnergyPvlibRequest(BaseModel):
    """Inputs for a pvlib (PVWatts) energy simulation.

    Tilt, azimuth, inverter efficiency, and system losses are optional;
    omitting them falls back to the Egypt-tuned defaults from
    ``app.config.settings`` and the canonical PVWatts loss factor.
    """

    location: Location
    system_kw: float = Field(..., gt=0, description="Nameplate DC capacity in kW")
    tilt_deg: float | None = Field(
        None,
        ge=0,
        le=90,
        description="Module tilt from horizontal (default: configured Cairo optimum)",
    )
    azimuth_deg: float | None = Field(
        None,
        ge=0,
        le=360,
        description="Module azimuth, 180° = south (default: configured value)",
    )
    inverter_efficiency: float | None = Field(
        None,
        gt=0,
        le=1,
        description="Constant AC/DC conversion efficiency (default: configured 0.96)",
    )
    system_losses_fraction: float | None = Field(
        None,
        ge=0,
        lt=1,
        description=(
            "Lumped DC-side losses (soiling, mismatch, wiring, nameplate, "
            "availability). Default: PVWatts canonical 0.14."
        ),
    )


class EnergyPvlibResult(BaseModel):
    """Headline output of a pvlib energy simulation.

    Hourly arrays are intentionally not serialised — 8 760 floats are
    heavy on the wire and the dashboard only needs annual + monthly
    rollups plus the performance metrics.
    """

    annual_kwh: float = Field(..., description="Annual AC energy delivered to the grid (kWh)")
    monthly_kwh: list[float] = Field(
        ...,
        min_length=12,
        max_length=12,
        description="12 calendar-month AC totals, January..December (kWh)",
    )
    specific_yield_kwh_per_kwp: float = Field(
        ...,
        description="Annual AC energy per kW of installed DC capacity (kWh/kWp). "
        "Cairo published range: ~1 700–1 900 kWh/kWp.",
    )
    capacity_factor: float = Field(
        ...,
        description="Annual AC energy / (DC capacity × 8 760 h). Cairo typical: 0.19–0.22.",
    )
    performance_ratio: float = Field(
        ...,
        description="Specific yield / reference yield. Well-designed systems: 0.75–0.85.",
    )
    poa_annual_kwh_per_m2: float = Field(
        ...,
        description="Annual plane-of-array irradiance — energy hitting the tilted module plane.",
    )
    mean_cell_temp_c: float = Field(..., description="Mean module cell temperature over the year")

    # Echoed assumptions so the JSON is self-documenting.
    system_kw: float
    tilt_deg: float
    azimuth_deg: float
    inverter_efficiency: float
    system_losses_fraction: float


class EnergyManualRequest(BaseModel):
    """Inputs for a manual physics-based energy simulation.

    Identical shape to :class:`EnergyPvlibRequest` so a frontend can
    reuse the same form for both endpoints. A separate class keeps the
    OpenAPI documentation crisp about which model is being invoked.
    """

    location: Location
    system_kw: float = Field(..., gt=0, description="Nameplate DC capacity in kW")
    tilt_deg: float | None = Field(
        None,
        ge=0,
        le=90,
        description="Module tilt from horizontal (default: configured Cairo optimum)",
    )
    azimuth_deg: float | None = Field(
        None,
        ge=0,
        le=360,
        description="Module azimuth, 180° = south (default: configured value)",
    )
    inverter_efficiency: float | None = Field(
        None,
        gt=0,
        le=1,
        description="Constant AC/DC conversion efficiency (default: configured 0.96)",
    )
    system_losses_fraction: float | None = Field(
        None,
        ge=0,
        lt=1,
        description=(
            "Lumped DC-side losses (soiling, mismatch, wiring, nameplate, "
            "availability). Default: PVWatts canonical 0.14."
        ),
    )


class EnergyManualResult(BaseModel):
    """Headline output of the manual physics simulation.

    Same fields as :class:`EnergyPvlibResult` so downstream consumers
    can treat the two interchangeably. The ``model`` discriminator
    field lets a comparison view tell them apart without re-inferring.
    """

    model: str = Field(
        default="manual",
        description="Discriminator identifying which energy chain produced this result.",
    )
    annual_kwh: float = Field(..., description="Annual AC energy delivered to the grid (kWh)")
    monthly_kwh: list[float] = Field(
        ...,
        min_length=12,
        max_length=12,
        description="12 calendar-month AC totals, January..December (kWh)",
    )
    specific_yield_kwh_per_kwp: float = Field(
        ...,
        description="Annual AC energy per kW of installed DC capacity (kWh/kWp). "
        "Cairo published range: ~1 700–1 900 kWh/kWp.",
    )
    capacity_factor: float = Field(
        ...,
        description="Annual AC energy / (DC capacity × 8 760 h). Cairo typical: 0.19–0.22.",
    )
    performance_ratio: float = Field(
        ...,
        description="Specific yield / reference yield. Well-designed systems: 0.75–0.85.",
    )
    poa_annual_kwh_per_m2: float = Field(
        ...,
        description="Annual plane-of-array irradiance — energy hitting the tilted module plane.",
    )
    mean_cell_temp_c: float = Field(..., description="Mean module cell temperature over the year")

    # Echoed assumptions so the JSON is self-documenting.
    system_kw: float
    tilt_deg: float
    azimuth_deg: float
    inverter_efficiency: float
    system_losses_fraction: float
