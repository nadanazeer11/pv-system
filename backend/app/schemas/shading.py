"""Schemas for the shading-geometry service.

Day-19 deliverable A: a deterministic, no-external-data inter-row spacing
calculator that replaces the inter-row-shading slice of the bulk 0.7
roof utilization factor with explicit geometry. Subsequent deliverables
(B: obstacle shadow sweep, C: horizon obstruction) will plug into the
same shading router with their own request/response schemas.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class InterRowSpacingRequest(BaseModel):
    """Inputs for the inter-row spacing calculation.

    Every field is optional — when omitted, the Egypt-tuned defaults
    from :pydata:`app.config.settings` are used so the endpoint can be
    called with an empty body to ask "what spacing does this project
    use by default?". Per-request overrides keep the service usable for
    sensitivity analysis and for non-Cairo locations.
    """

    panel_slope_height_m: float | None = Field(
        None,
        gt=0,
        le=5,
        description=(
            "Slope-direction dimension of the panel in metres — the long "
            "edge for portrait orientation. Default: configured panel "
            "slope height."
        ),
    )
    tilt_deg: float | None = Field(
        None,
        ge=0,
        le=89,
        description=(
            "Panel tilt above horizontal. Default: configured Egypt tilt "
            "(latitude optimum ≈ 26°). Tilt = 0 means flat panels (no "
            "inter-row shading)."
        ),
    )
    sun_elevation_deg: float | None = Field(
        None,
        gt=0,
        le=90,
        description=(
            "Worst-case sun elevation used to size the row pitch. Lower "
            "values → longer shadows → wider pitch → fewer panels per m². "
            "Default: configured Cairo design value (22°, December "
            "solstice ~9 am)."
        ),
    )


class InterRowSpacingResult(BaseModel):
    """Output of the inter-row spacing calculation.

    Echoes the assumptions used so a downstream caller (or a thesis
    reviewer reading the JSON) can reproduce the math without consulting
    the server config.
    """

    row_pitch_m: float = Field(
        ...,
        description="Centre-to-centre distance between consecutive panel rows.",
    )
    panel_footprint_m: float = Field(
        ...,
        description="Ground projection of one tilted panel along the slope.",
    )
    shadow_length_m: float = Field(
        ...,
        description="Length of the shadow cast behind the panel at the design sun elevation.",
    )
    inter_row_density_factor: float = Field(
        ...,
        gt=0,
        le=1,
        description=(
            "Dimensionless area factor: panel_footprint / row_pitch. "
            "Multiply by the gross roof area to get the area available "
            "for panels after subtracting the inter-row gap."
        ),
    )
    panel_slope_height_m: float
    tilt_deg: float
    sun_elevation_deg: float
