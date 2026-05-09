"""Shading-geometry service.

Day-19 deliverable A: deterministic inter-row spacing geometry, the
cheap-and-explicit replacement for the inter-row component of the
bulk 0.7 roof utilization factor used in :mod:`app.services.pv_sizing`.

Why a separate service?
-----------------------
The Day-3 sizing kernel folds inter-row shading into a single 0.7
multiplier alongside walkways, edge setbacks and bulk obstructions.
That number is defensible at the order-of-magnitude level but cannot be
audited at the methodology-section level: a thesis reviewer cannot tell
*how much* of the 30 % loss is shading vs. walkways vs. the water tank.
This service exposes the inter-row component as a closed-form geometric
factor that depends only on three physical inputs (panel slope height,
tilt, design sun elevation), so future work can subtract it from the
bulk factor and stack it explicitly with the obstacle and horizon
shading kernels (deliverables B and C).

Geometry
--------
A panel of slope-direction height ``h`` tilted at angle ``β`` above
horizontal projects two distances on the ground:

* Its own footprint along the slope:    ``f = h · cos(β)``
* The shadow cast behind it when the sun is at elevation ``α``:
                                         ``s = h · sin(β) / tan(α)``

The required centre-to-centre row pitch is ``p = f + s`` — closer than
that and the panel behind would be shaded during the design hour.
The dimensionless density factor ``f / p`` is the fraction of
roof-area-along-slope that actually sits under panels; ``1 − f/p`` is
the inter-row gap loss.

For a 1.8 m panel at 26° tilt with the sun at 22° (Cairo December-
solstice 9 am) this gives ``p ≈ 3.6 m`` and ``density ≈ 0.45``.
A deeper-winter / earlier-morning sun lowers the elevation and widens
the pitch, recovering less of the roof for panels but guaranteeing
zero self-shading during productive hours.

Reference: NREL "Best Practices in PV System Installation" (2021); the
formula is the standard portrait-mounted residential-PV inter-row rule
used throughout the pre-feasibility literature and reproduced in
Mahmoud & El-Nokali (2023, Egyptian rooftop PV pre-feasibility studies).
"""
from __future__ import annotations

import math

from app.config import settings
from app.schemas.shading import InterRowSpacingRequest, InterRowSpacingResult


class ShadingError(ValueError):
    """Raised when shading inputs produce a degenerate geometry."""


def compute_inter_row_spacing(
    request: InterRowSpacingRequest,
) -> InterRowSpacingResult:
    """Compute the row pitch and density factor from panel + sun geometry.

    Parameters
    ----------
    request : InterRowSpacingRequest
        Optional per-request overrides. Any field left as ``None`` falls
        back to the Egypt-tuned default in :pydata:`app.config.settings`.

    Returns
    -------
    InterRowSpacingResult
        Echoes the assumptions used so the response is self-documenting.
    """
    panel_h = request.panel_slope_height_m or settings.panel_slope_height_m
    tilt_deg = (
        request.tilt_deg
        if request.tilt_deg is not None
        else settings.default_tilt_deg
    )
    sun_elev_deg = (
        request.sun_elevation_deg
        if request.sun_elevation_deg is not None
        else settings.design_sun_elevation_deg
    )

    tilt_rad = math.radians(tilt_deg)
    sun_rad = math.radians(sun_elev_deg)

    footprint = panel_h * math.cos(tilt_rad)

    # Flat panels (tilt == 0) cast no inter-row shadow — every panel
    # sits in its own footprint and the density factor collapses to 1.
    # The general formula reduces to the same answer in the limit, but
    # an explicit branch keeps the result exact at the boundary and
    # avoids a 0 / tan(small) numerical artefact.
    if tilt_deg == 0:
        return InterRowSpacingResult(
            row_pitch_m=footprint,
            panel_footprint_m=footprint,
            shadow_length_m=0.0,
            inter_row_density_factor=1.0,
            panel_slope_height_m=panel_h,
            tilt_deg=tilt_deg,
            sun_elevation_deg=sun_elev_deg,
        )

    shadow_length = panel_h * math.sin(tilt_rad) / math.tan(sun_rad)
    pitch = footprint + shadow_length
    density = footprint / pitch

    return InterRowSpacingResult(
        row_pitch_m=pitch,
        panel_footprint_m=footprint,
        shadow_length_m=shadow_length,
        inter_row_density_factor=density,
        panel_slope_height_m=panel_h,
        tilt_deg=tilt_deg,
        sun_elevation_deg=sun_elev_deg,
    )
