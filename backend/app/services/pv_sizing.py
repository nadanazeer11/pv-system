"""PV system sizing.

Translates a flat roof area in square metres into a discrete panel
count and a nameplate DC system capacity in kilowatts. This is the
bridge between the roof-detection pipeline (Days 10–11), which produces
an area, and the energy models (Days 4–5), which consume a system size.

Method
------
The sizing follows the simple area-based rule used in the bulk of the
Egyptian rooftop PV literature for residential pre-feasibility studies::

    usable_area  = roof_area * roof_utilization_factor
    panel_count  = floor(usable_area / panel_area)
    system_kw    = panel_count * panel_rated_watts / 1000

The **roof utilization factor** (default 0.7) is a published
rule-of-thumb that lumps together several physical losses that would
otherwise need explicit geometric modelling:

  * Edge setbacks required by Egyptian fire and maintenance codes.
  * Walkway access between panel rows for cleaning (a relevant loss in
    Cairo's high-soiling environment).
  * Inter-row shading spacing for tilted mounts (panels at 26° tilt
    cast morning/afternoon shadows that would steal yield from the next
    row if packed tightly).
  * Roof-mounted obstructions: water tanks, satellite dishes, parapet
    walls, HVAC condensers — extremely common on Egyptian residential
    rooftops.

Geometric-shading mode
----------------------
When the caller supplies an explicit ``inter_row_density_factor`` —
typically computed by :mod:`app.services.shading` from the panel tilt,
slope height and a worst-case sun elevation — the sizing kernel
switches to::

    util = roof_utilization_excl_inter_row × inter_row_density_factor

so the inter-row loss is counted *exactly once* with the geometry the
caller chose, and the bulk 0.7 (which bundles a generic inter-row
assumption) is not double-discounted. An explicit
``roof_utilization_factor`` on the request still overrides everything.

Future work
-----------
Days 10–11 (roof_detection) will replace the bulk utilization factor
with a polygon-clipping geometric model that explicitly subtracts
obstructions detected from satellite imagery. Until then, the 0.7
constant gives the right order of magnitude (see e.g. Mahmoud &
El-Nokali, 2023, Egyptian rooftop PV pre-feasibility studies).

Why floor (not round)?
----------------------
A fractional panel is physically meaningless — you cannot install 12.7
panels. Rounding **down** is the conservative, installer-realistic
choice: a system spec that promises capacity the roof cannot actually
hold would propagate an upward bias through every downstream financial
metric.
"""
from __future__ import annotations

import math

from app.config import settings
from app.schemas.sizing import SizingRequest, SizingResult


class SizingError(ValueError):
    """Raised when sizing inputs are physically impossible."""


def compute_system_size(request: SizingRequest) -> SizingResult:
    """Compute panel count and DC system capacity from a roof area.

    Parameters
    ----------
    request : SizingRequest
        Roof area plus optional hardware overrides. Any field left as
        ``None`` falls back to the Egypt-tuned default in
        :pydata:`app.config.settings`.

    Returns
    -------
    SizingResult
        Echoes the assumptions used so the response is self-documenting.

    Raises
    ------
    SizingError
        If, after applying the utilization factor, the usable area is
        smaller than a single panel — the rooftop cannot host even one
        module and the caller should be told explicitly rather than
        receiving a silent zero.
    """
    panel_w = request.panel_rated_watts or settings.panel_rated_watts
    panel_area = request.panel_area_m2 or settings.panel_area_m2

    # Three precedence rules for the utilization factor — in order:
    #   1. An explicit `roof_utilization_factor` on the request always
    #      wins (caller knows what they're doing; overrides everything).
    #   2. Otherwise, if the caller supplied an explicit
    #      `inter_row_density_factor`, switch to the geometric-shading
    #      formula:
    #          util = roof_utilization_excl_inter_row × inter_row_density
    #      so the inter-row loss is counted exactly once and the bulk
    #      0.7 — which already bundles inter-row implicitly — is not
    #      double-discounted.
    #   3. Otherwise, fall back to the bulk default (0.7).
    if request.roof_utilization_factor is not None:
        utilization = request.roof_utilization_factor
    elif request.inter_row_density_factor is not None:
        utilization = (
            settings.roof_utilization_excl_inter_row
            * request.inter_row_density_factor
        )
    else:
        utilization = settings.roof_utilization_factor

    usable_area = request.roof_area_m2 * utilization

    if usable_area < panel_area:
        raise SizingError(
            f"Usable roof area {usable_area:.2f} m² is smaller than a single panel "
            f"({panel_area:.2f} m²). No PV system can be installed."
        )

    panel_count = math.floor(usable_area / panel_area)
    system_kw = panel_count * panel_w / 1000.0
    panel_density = (panel_count * panel_w) / usable_area if usable_area > 0 else 0.0

    return SizingResult(
        roof_area_m2=request.roof_area_m2,
        usable_roof_area_m2=usable_area,
        panel_count=panel_count,
        system_kw=system_kw,
        panel_rated_watts=panel_w,
        panel_area_m2=panel_area,
        roof_utilization_factor=utilization,
        inter_row_density_factor=request.inter_row_density_factor,
        panel_density_w_per_m2=panel_density,
    )
