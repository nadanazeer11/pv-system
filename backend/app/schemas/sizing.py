"""Schemas for the PV sizing endpoint.

A standalone request/response pair so the frontend can call sizing in
isolation (e.g. "how big a system fits on this roof?") before committing
to a full estimate. The result intentionally echoes the assumptions
used in the calculation to make the response self-documenting and
auditable from the API surface alone.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SizingRequest(BaseModel):
    """Inputs for the PV sizing calculation.

    All hardware fields are optional — when omitted, the Egypt-tuned
    defaults from `app.config.settings` are used. Allowing per-request
    overrides keeps the service usable for sensitivity analysis and for
    future "what-if" UI controls without touching the service code.
    """

    roof_area_m2: float = Field(..., gt=0, description="Total available roof area in square metres")
    panel_rated_watts: float | None = Field(
        None,
        gt=0,
        description="Per-panel STC rating in watts (default: configured Egypt panel rating)",
    )
    panel_area_m2: float | None = Field(
        None,
        gt=0,
        description="Per-panel physical area in square metres (default: configured panel area)",
    )
    roof_utilization_factor: float | None = Field(
        None,
        gt=0,
        le=1,
        description=(
            "Fraction of roof area usable for panels after deducting "
            "walkways, obstacles, edge setbacks and inter-row shading "
            "spacing (default: configured value)"
        ),
    )
    inter_row_density_factor: float | None = Field(
        None,
        gt=0,
        le=1,
        description=(
            "Optional explicit inter-row shading density (footprint / "
            "row pitch) computed by /api/shading/inter-row. When supplied "
            "and `roof_utilization_factor` is left at its default, the "
            "sizing kernel switches to `roof_utilization_excl_inter_row × "
            "inter_row_density_factor` so the inter-row loss is counted "
            "exactly once. When `roof_utilization_factor` is supplied "
            "explicitly the override wins and this field is ignored."
        ),
    )


class SizingResult(BaseModel):
    """Output of the PV sizing calculation.

    Echoes the assumptions used so a downstream caller (or a thesis
    reviewer reading the JSON) can reproduce the math without consulting
    the server config.
    """

    roof_area_m2: float = Field(..., description="Roof area submitted by the caller")
    usable_roof_area_m2: float = Field(..., description="Roof area available for panels after utilization factor")
    panel_count: int = Field(..., ge=0, description="Whole panels that physically fit on the usable area")
    system_kw: float = Field(..., ge=0, description="Nameplate DC system capacity in kilowatts")

    panel_rated_watts: float = Field(..., description="Per-panel STC rating used in the calculation")
    panel_area_m2: float = Field(..., description="Per-panel area used in the calculation")
    roof_utilization_factor: float = Field(..., description="Utilization factor used in the calculation")
    inter_row_density_factor: float | None = Field(
        None,
        description=(
            "Echo of the inter-row density factor supplied by the caller. "
            "Null when geometric shading was not applied — the inter-row "
            "loss is then bundled inside `roof_utilization_factor`."
        ),
    )
    panel_density_w_per_m2: float = Field(
        ...,
        description="Effective system DC density (system watts per square metre of usable roof)",
    )
