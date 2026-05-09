"""Load-profile-driven PV sizing.

Inverts the area-based sizing flow: turns an appliance list into a
daily energy demand, then back-calculates the DC system kW that would
cover it under Egyptian peak-sun conditions, and checks whether the
required roof area fits the building.

Method
------
For each appliance line `(watts, hours_per_day, quantity)`::

    daily_kwh = quantity * watts * hours_per_day / 1000
    peak_kw   = quantity * watts / 1000

The household totals are sums of those columns. The recommended DC
system size is then::

    target_daily_kwh = total_daily_kwh * coverage_fraction
    system_kw        = target_daily_kwh / (peak_sun_hours * performance_ratio)

`peak_sun_hours` is the Cairo annual-average value (5.5 kWh/m²/day at
the latitude-tilt optimum, per PVGIS); `performance_ratio` is the
industry-standard derate factor that bundles inverter efficiency,
soiling, mismatch and wiring losses (~0.78 for Egyptian residential
rooftop PV per IEA-PVPS Task 13). The result is a deliberately simple
PSH-based sizing rule, not a full pvlib run — it answers "how big a
system do I need?" cheaply enough to recompute on every keystroke,
while the canonical `/api/energy/pvlib` chain remains available for
validated yield numbers once a size is chosen.

Roof area derivation
--------------------
The recommended panel count is `ceil(system_kw / panel_kw)` — *ceil*
not floor, because we are sizing *up* to meet a load (the inverse of
`pv_sizing.compute_system_size`, which floors *down* to fit a roof).
The required gross roof area is then::

    required_area = panel_count * panel_area_m2 / utilization_factor

so the answer matches the area the standard area-based sizer would
need as input to produce the same system. When `available_roof_area_m2`
is supplied we report whether the recommendation physically fits.
"""
from __future__ import annotations

import math

from app.config import settings
from app.schemas.load_sizing import (
    ApplianceLibraryEntry,
    LoadSizingRequest,
    LoadSizingResult,
)


class LoadSizingError(ValueError):
    """Raised when the load profile cannot be sized into a real system."""


# ─────────────────────────────────────────────────────────────────────────
# Egyptian residential appliance library.
#
# Wattages are *typical continuous-draw* figures for the dominant model
# class sold in the Egyptian market. Sources triangulated across:
#   * EgyptERA consumer-energy-efficiency leaflets (2022 edition);
#   * Carrier / LG / Toshiba EG product datasheets for split-AC SKUs
#     in the 1.5–2.5 ton range that dominate Egyptian residential
#     installs;
#   * IEA 4E TCP residential-appliance benchmarks (for items where
#     the local market is dominated by international SKUs at standard
#     ratings — fridges, washing machines, microwaves).
#
# `typical_hours_per_day` reflects Egyptian usage patterns (long AC
# duty cycles in summer, evening-heavy lighting, mid-day cooking) and
# is intentionally an annual-average so the UI stays a single number.
# Users are expected to override these — the library exists so the
# form is never blank.
# ─────────────────────────────────────────────────────────────────────────
APPLIANCE_LIBRARY: list[ApplianceLibraryEntry] = [
    # Cooling (the dominant Egyptian residential load)
    ApplianceLibraryEntry(name="Air conditioner (1.5 ton split)", watts=1500, typical_hours_per_day=6, category="Cooling"),
    ApplianceLibraryEntry(name="Air conditioner (2.25 ton split)", watts=2200, typical_hours_per_day=6, category="Cooling"),
    ApplianceLibraryEntry(name="Air conditioner (3 ton split)", watts=3000, typical_hours_per_day=6, category="Cooling"),
    ApplianceLibraryEntry(name="Ceiling fan", watts=75, typical_hours_per_day=8, category="Cooling"),
    ApplianceLibraryEntry(name="Standing / pedestal fan", watts=60, typical_hours_per_day=6, category="Cooling"),
    # Refrigeration (always-on)
    ApplianceLibraryEntry(name="Refrigerator (medium)", watts=150, typical_hours_per_day=10, category="Refrigeration"),
    ApplianceLibraryEntry(name="Refrigerator (large / side-by-side)", watts=250, typical_hours_per_day=10, category="Refrigeration"),
    ApplianceLibraryEntry(name="Standalone freezer", watts=200, typical_hours_per_day=10, category="Refrigeration"),
    # Lighting
    ApplianceLibraryEntry(name="LED bulb (10 W)", watts=10, typical_hours_per_day=5, category="Lighting"),
    ApplianceLibraryEntry(name="CFL bulb (20 W)", watts=20, typical_hours_per_day=5, category="Lighting"),
    # Kitchen
    ApplianceLibraryEntry(name="Microwave oven", watts=1100, typical_hours_per_day=0.3, category="Kitchen"),
    ApplianceLibraryEntry(name="Electric oven", watts=2500, typical_hours_per_day=0.5, category="Kitchen"),
    ApplianceLibraryEntry(name="Electric kettle", watts=1800, typical_hours_per_day=0.2, category="Kitchen"),
    ApplianceLibraryEntry(name="Dishwasher", watts=1500, typical_hours_per_day=1, category="Kitchen"),
    ApplianceLibraryEntry(name="Toaster", watts=900, typical_hours_per_day=0.1, category="Kitchen"),
    # Water heating
    ApplianceLibraryEntry(name="Electric water heater (50 L)", watts=2000, typical_hours_per_day=2, category="Water heating"),
    ApplianceLibraryEntry(name="Electric water heater (80 L)", watts=2500, typical_hours_per_day=2, category="Water heating"),
    # Laundry
    ApplianceLibraryEntry(name="Washing machine", watts=500, typical_hours_per_day=1, category="Laundry"),
    ApplianceLibraryEntry(name="Clothes dryer", watts=2500, typical_hours_per_day=0.5, category="Laundry"),
    ApplianceLibraryEntry(name="Iron", watts=1100, typical_hours_per_day=0.3, category="Laundry"),
    # Entertainment / electronics
    ApplianceLibraryEntry(name="LED TV (50\")", watts=100, typical_hours_per_day=4, category="Electronics"),
    ApplianceLibraryEntry(name="Desktop computer", watts=200, typical_hours_per_day=4, category="Electronics"),
    ApplianceLibraryEntry(name="Laptop", watts=65, typical_hours_per_day=4, category="Electronics"),
    ApplianceLibraryEntry(name="Wi-Fi router / modem", watts=10, typical_hours_per_day=24, category="Electronics"),
    # Other
    ApplianceLibraryEntry(name="Hair dryer", watts=1500, typical_hours_per_day=0.1, category="Other"),
    ApplianceLibraryEntry(name="Vacuum cleaner", watts=1400, typical_hours_per_day=0.2, category="Other"),
    ApplianceLibraryEntry(name="Water pump", watts=750, typical_hours_per_day=1, category="Other"),
]


def get_appliance_library() -> list[ApplianceLibraryEntry]:
    """Return the seeded appliance library."""
    return list(APPLIANCE_LIBRARY)


def compute_load_sizing(request: LoadSizingRequest) -> LoadSizingResult:
    """Size a system to cover an appliance load profile."""
    panel_w = request.panel_rated_watts or settings.panel_rated_watts
    panel_area = request.panel_area_m2 or settings.panel_area_m2
    utilization = (
        request.roof_utilization_factor
        if request.roof_utilization_factor is not None
        else settings.roof_utilization_factor
    )

    daily_kwh = 0.0
    peak_kw = 0.0
    for entry in request.appliances:
        daily_kwh += entry.quantity * entry.watts * entry.hours_per_day / 1000.0
        peak_kw += entry.quantity * entry.watts / 1000.0

    if daily_kwh <= 0:
        raise LoadSizingError(
            "Total daily load is zero — every appliance has hours_per_day=0. "
            "Increase usage hours on at least one appliance."
        )

    psh = settings.egypt_peak_sun_hours
    pr = settings.system_performance_ratio

    target_daily_kwh = daily_kwh * request.coverage_fraction
    system_kw = target_daily_kwh / (psh * pr)

    panel_kw = panel_w / 1000.0
    panel_count = math.ceil(system_kw / panel_kw)
    # Snap reported system_kw to the integer-panel reality so the
    # downstream area derivation and the dashboard's "N panels at X W"
    # subtitle stay arithmetically consistent.
    system_kw_snapped = panel_count * panel_kw
    required_roof_area = panel_count * panel_area / utilization

    roof_fits: bool | None = None
    shortfall: float | None = None
    if request.available_roof_area_m2 is not None:
        roof_fits = request.available_roof_area_m2 >= required_roof_area
        if not roof_fits:
            shortfall = required_roof_area - request.available_roof_area_m2

    return LoadSizingResult(
        daily_load_kwh=daily_kwh,
        monthly_load_kwh=daily_kwh * 30.4,
        annual_load_kwh=daily_kwh * 365.0,
        peak_load_kw=peak_kw,
        recommended_system_kw=system_kw_snapped,
        recommended_panel_count=panel_count,
        required_roof_area_m2=required_roof_area,
        coverage_fraction=request.coverage_fraction,
        peak_sun_hours=psh,
        performance_ratio=pr,
        panel_rated_watts=panel_w,
        panel_area_m2=panel_area,
        roof_utilization_factor=utilization,
        roof_fits=roof_fits,
        available_roof_area_m2=request.available_roof_area_m2,
        roof_area_shortfall_m2=shortfall,
    )
