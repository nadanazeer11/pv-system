"""pvlib-based energy generation model (PVWatts approach).

Day 4 deliverable: take a TMY hourly weather frame and a system size, and
return how many kilowatt-hours the array will produce over a typical year.
This is the **industry-standard reference model** half of the dual-energy
backbone of the thesis. Day 5's manual physics model will be cross-validated
against the output of this module.

Method (functional PVWatts chain)
---------------------------------
We use pvlib's individual building blocks rather than the high-level
``ModelChain`` so each step is explicit, inspectable, and traceable in the
methodology section of the thesis:

1. **Solar position** — :func:`pvlib.solarposition.get_solarposition`
   gives the apparent zenith and azimuth of the sun at every TMY timestamp
   for the site's lat/lon.
2. **Plane-of-array (POA) irradiance** —
   :func:`pvlib.irradiance.get_total_irradiance` transposes the horizontal
   irradiance components (GHI/DNI/DHI) onto the tilted module plane using
   the Hay-Davies sky-diffuse model (pvlib default, well-validated for
   sub-tropical clear-sky climates such as Egypt).
3. **Cell temperature** — :func:`pvlib.temperature.sapm_cell` with the
   SAPM ``open_rack_glass_polymer`` parameter set, the standard choice
   for free-standing rooftop installations of crystalline-silicon
   modules — the dominant technology in the Egyptian market.
4. **DC power** — :func:`pvlib.pvsystem.pvwatts_dc` applies the linear
   PVWatts model ``pdc = (G_poa / 1000) · pdc0 · (1 + γ·(T_cell − 25))``
   with ``γ = −0.0035 / °C`` (typical for monocrystalline silicon).
5. **System DC losses** — a single combined-losses factor folds in
   soiling, mismatch, wiring, and module-nameplate tolerance. Defaults
   to NREL's PVWatts canonical 14 %, exposed as a parameter so the
   sensitivity analysis (Week 3) can sweep it.
6. **AC conversion** — :func:`pvlib.inverter.pvwatts` clips at the
   inverter nominal AC capacity using a constant efficiency
   (``inverter_efficiency`` from config, 96 %). DC-to-AC ratio is held
   at 1.0 in this baseline; oversizing studies are deferred to Week 3.

Why these choices
-----------------
* PVWatts is the model of record for residential / small-commercial PV
  pre-feasibility (NREL, 2014). It is the dominant model in published
  Egyptian rooftop PV studies, which makes our results directly
  comparable to that literature in the validation section.
* The Hay-Davies sky-diffuse model balances accuracy against simplicity
  and is the pvlib default. The Perez model is marginally more accurate
  in cloudy climates but offers little improvement in Egypt's high-DNI
  sky and adds opaque tuning constants.
* We deliberately do **not** use ``ModelChain``: every line of the
  pipeline below maps to one step in the methodology section of the
  thesis. A black-box chain would be convenient but unauditable.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pvlib

from app.config import settings


# Temperature coefficient of power for monocrystalline silicon modules.
# Typical published value for c-Si modules used in PVWatts (NREL, 2014).
GAMMA_PDC = -0.0035  # 1/°C

# pvlib's SAPM cell-temperature model parameter set for an open-rack,
# glass-polymer module (the standard choice for free-standing rooftop
# c-Si installations).
SAPM_THERMAL_PARAMS = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"][
    "open_rack_glass_polymer"
]

# NREL PVWatts canonical combined system loss (excluding inverter):
# soiling 2 % + shading 3 % + mismatch 2 % + wiring 2 % + connections 0.5 %
# + LID 1.5 % + nameplate 1 % + availability 3 % ≈ 14 %.
# Egypt would usually argue for higher soiling, so this is a defensible
# floor — Week 3's sensitivity sweep will perturb it.
DEFAULT_SYSTEM_LOSSES_FRACTION = 0.14


class EnergyModelError(ValueError):
    """Raised when the energy simulation receives inconsistent inputs."""


@dataclass(frozen=True)
class EnergySimulation:
    """In-memory result of one PVWatts simulation.

    Kept as a dataclass (not a Pydantic model) because the hourly arrays
    are pandas-native and we don't want to pay the validation cost on
    every 8 760-row Series. The router-facing schema in
    ``app.schemas.energy`` is the serialisable view.
    """

    annual_kwh: float
    monthly_kwh: list[float]  # 12 entries, Jan..Dec
    specific_yield_kwh_per_kwp: float
    capacity_factor: float
    performance_ratio: float
    poa_annual_kwh_per_m2: float
    mean_cell_temp_c: float
    ac_hourly: pd.Series  # AC power in W, indexed by TMY timestamp


def simulate(
    tmy: pd.DataFrame,
    *,
    latitude: float,
    longitude: float,
    system_kw: float,
    tilt_deg: float | None = None,
    azimuth_deg: float | None = None,
    inverter_efficiency: float | None = None,
    system_losses_fraction: float = DEFAULT_SYSTEM_LOSSES_FRACTION,
) -> EnergySimulation:
    """Run a full PVWatts simulation against a TMY.

    Parameters
    ----------
    tmy
        Hourly DataFrame in pvlib canonical form: columns ``ghi``,
        ``dni``, ``dhi``, ``temp_air``, ``wind_speed`` and a tz-aware
        ``DatetimeIndex``. Produced by ``app.services.pvgis_service``.
    latitude, longitude
        Site coordinates in decimal degrees. Required for the solar
        position calculation — the TMY irradiance values alone are not
        enough.
    system_kw
        Nameplate DC capacity in kW. Comes from
        :mod:`app.services.pv_sizing`.
    tilt_deg, azimuth_deg
        Panel orientation. Default to ``settings.default_tilt_deg`` (26°,
        Cairo latitude optimum) and ``settings.default_azimuth_deg``
        (180° = south).
    inverter_efficiency
        Constant AC/DC conversion efficiency. Defaults to
        ``settings.inverter_efficiency`` (96 %, modern grid-tied
        inverters).
    system_losses_fraction
        Lumped DC-side derate (soiling, mismatch, wiring, nameplate
        tolerance, availability). PVWatts default 14 %.

    Returns
    -------
    EnergySimulation
        Annual and monthly AC energy plus a few headline performance
        metrics (capacity factor, performance ratio, specific yield).
        See :class:`EnergySimulation` for the full set.

    Raises
    ------
    EnergyModelError
        If the TMY frame is empty, the system size is non-positive, or
        the loss fraction is outside ``[0, 1)``.
    """
    if tmy.empty:
        raise EnergyModelError("TMY DataFrame is empty — nothing to simulate")
    if system_kw <= 0:
        raise EnergyModelError(f"system_kw must be positive, got {system_kw}")
    if not 0.0 <= system_losses_fraction < 1.0:
        raise EnergyModelError(
            "system_losses_fraction must be in [0, 1), got "
            f"{system_losses_fraction}"
        )

    tilt = settings.default_tilt_deg if tilt_deg is None else tilt_deg
    azimuth = settings.default_azimuth_deg if azimuth_deg is None else azimuth_deg
    eta_inv = (
        settings.inverter_efficiency if inverter_efficiency is None else inverter_efficiency
    )
    pdc0_w = system_kw * 1000.0  # nameplate DC, W

    # 1) Solar position at every TMY timestamp.
    solpos = pvlib.solarposition.get_solarposition(tmy.index, latitude, longitude)

    # 2) POA irradiance (Hay-Davies sky-diffuse model is pvlib's default).
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=tmy["dni"],
        ghi=tmy["ghi"],
        dhi=tmy["dhi"],
    )
    poa_global = poa["poa_global"].fillna(0.0).clip(lower=0.0)

    # 3) Cell temperature via SAPM open-rack glass-polymer parameters.
    temp_cell = pvlib.temperature.sapm_cell(
        poa_global=poa_global,
        temp_air=tmy["temp_air"],
        wind_speed=tmy["wind_speed"],
        **SAPM_THERMAL_PARAMS,
    )

    # 4) DC power from PVWatts (W).
    dc_w = pvlib.pvsystem.pvwatts_dc(
        g_poa_effective=poa_global,
        temp_cell=temp_cell,
        pdc0=pdc0_w,
        gamma_pdc=GAMMA_PDC,
    ).fillna(0.0).clip(lower=0.0)

    # 5) System DC losses (soiling, mismatch, wiring, nameplate, etc.).
    dc_w_after_losses = dc_w * (1.0 - system_losses_fraction)

    # 6) AC conversion. Inverter nominal AC = nameplate DC (DC:AC = 1.0).
    ac_w = pvlib.inverter.pvwatts(
        pdc=dc_w_after_losses,
        pdc0=pdc0_w,
        eta_inv_nom=eta_inv,
    ).fillna(0.0).clip(lower=0.0)

    # Energy aggregations. TMY frequency is hourly, so 1 W·h = 1 W × 1 h
    # and dividing by 1 000 gives kWh.
    hourly_kwh = ac_w / 1000.0
    annual_kwh = float(hourly_kwh.sum())
    monthly_kwh = _aggregate_monthly_kwh(hourly_kwh)

    poa_annual_kwh_per_m2 = float(poa_global.sum() / 1000.0)
    hours = len(tmy)
    capacity_factor = annual_kwh / (system_kw * hours) if hours else 0.0
    specific_yield = annual_kwh / system_kw  # kWh per kWp
    # PR = specific yield / reference yield, where reference yield =
    # POA insolation in kWh/m² divided by STC irradiance (1 kW/m²).
    performance_ratio = (
        specific_yield / poa_annual_kwh_per_m2 if poa_annual_kwh_per_m2 > 0 else 0.0
    )

    return EnergySimulation(
        annual_kwh=annual_kwh,
        monthly_kwh=monthly_kwh,
        specific_yield_kwh_per_kwp=specific_yield,
        capacity_factor=capacity_factor,
        performance_ratio=performance_ratio,
        poa_annual_kwh_per_m2=poa_annual_kwh_per_m2,
        mean_cell_temp_c=float(temp_cell.mean()),
        ac_hourly=ac_w,
    )


def _aggregate_monthly_kwh(hourly_kwh: pd.Series) -> list[float]:
    """Sum hourly kWh into 12 calendar-month totals (Jan..Dec).

    TMY months are by construction "typical" months, possibly drawn from
    different historical years; the index month is what matters, not its
    year. We therefore group by ``index.month`` and reindex 1..12 so a
    month with zero generation (impossible in Egypt, but defensive) is
    still represented as 0 instead of dropped.
    """
    by_month = hourly_kwh.groupby(hourly_kwh.index.month).sum()
    by_month = by_month.reindex(range(1, 13), fill_value=0.0)
    return [float(v) for v in by_month.values]
