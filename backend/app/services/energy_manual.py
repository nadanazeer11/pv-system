"""Manual physics-based energy model — first-principles cross-validation
twin of :mod:`app.services.energy_pvlib`.

This module deliberately uses **no** :mod:`pvlib` calls. Every step is
implemented from textbook equations so a thesis reviewer can verify each
line against its citation. The pvlib-based model and this manual model
together form the "dual energy" methodological backbone of the thesis:
two independent chains pointed at the same TMY whose disagreement
quantifies model uncertainty.

Method (functional chain mirroring the pvlib service)
-----------------------------------------------------
1. **Solar geometry** — Cooper's (1969) declination, Spencer's (1971)
   equation of time, classical hour angle and spherical-trig formulas
   for solar zenith and azimuth. References: Duffie & Beckman, *Solar
   Engineering of Thermal Processes*, 4th ed., chapter 1.
2. **Plane-of-array (POA) irradiance** — Liu & Jordan (1960) isotropic
   sky-diffuse model. We deliberately pick **isotropic**, not the
   anisotropic Hay-Davies model used by pvlib, so the two chains
   disagree at this step. The disagreement is exactly what the
   validation chapter wants to measure.
3. **Cell temperature** — NOCT (Nominal Operating Cell Temperature)
   model: ``T_cell = T_air + (NOCT - 20)/800 · G_poa``. NOCT = 45 °C is
   the typical c-Si module spec-sheet value. This is the alternative to
   the SAPM open-rack model used by pvlib — same family, different
   parameterisation.
4. **DC power** — explicit single-diode-free linear PVWatts equation
   ``P_dc = (G_poa / 1000) · P_dc0 · (1 + γ·(T_cell − 25))`` with
   ``γ = −0.0035 /°C`` for monocrystalline silicon.
5. **System DC losses** — same lumped factor as the pvlib chain
   (default 14 %, NREL canonical) so any divergence between the two
   models is attributable to the irradiance/temperature pipeline only.
6. **AC conversion** — constant inverter efficiency, DC:AC = 1.0.

Why this matters
----------------
A single energy model is a single point of failure in a pre-feasibility
study. Pairing pvlib (SAPM + Hay-Davies) with a hand-rolled chain
(NOCT + Liu-Jordan) tells the thesis reviewer how much of the
predicted yield is robust across modelling assumptions and how much is
parameter-sensitive. The **same call signature** as :func:`energy_pvlib.simulate`
is intentional: the upcoming dual-energy comparison view (Day 15) is a
one-line diff between the two ``EnergySimulation`` objects.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import settings


# Temperature coefficient of power for monocrystalline silicon (1/°C).
# Matches the value used in the pvlib chain so the *only* differences
# between the two models live in the irradiance and cell-temp steps.
GAMMA_PDC = -0.0035

# Nominal Operating Cell Temperature (°C). Manufacturer spec for typical
# crystalline-silicon modules at 800 W/m², 20 °C ambient, 1 m/s wind.
# Sources: IEC 61215; NREL SAM defaults.
NOCT_C = 45.0

# Ground reflectance (dimensionless). 0.20 is the PVWatts and SAM
# default for mixed urban/grass surfaces — a reasonable approximation
# for Cairo rooftops.
GROUND_ALBEDO = 0.20

# NREL PVWatts canonical lumped DC-side loss factor. Same default as
# the pvlib service so cross-validation isolates physics differences.
DEFAULT_SYSTEM_LOSSES_FRACTION = 0.14


class EnergyModelError(ValueError):
    """Raised when the manual simulation receives inconsistent inputs."""


@dataclass(frozen=True)
class EnergySimulation:
    """In-memory result of one manual physics simulation.

    Same dataclass shape as :class:`app.services.energy_pvlib.EnergySimulation`
    so downstream consumers (financial model, comparison view) can treat
    the two models interchangeably.
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
    """Run a from-first-principles PV simulation against a TMY.

    Parameters mirror :func:`app.services.energy_pvlib.simulate` exactly
    so the two models are drop-in interchangeable. See module docstring
    for the chain and citations.

    Raises
    ------
    EnergyModelError
        If the TMY is empty, the system size is non-positive, or the
        loss fraction is outside ``[0, 1)``.
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
        settings.inverter_efficiency
        if inverter_efficiency is None
        else inverter_efficiency
    )
    pdc0_w = system_kw * 1000.0  # nameplate DC, W

    # 1) Solar position at every TMY timestamp.
    zenith_deg, sol_az_deg = _solar_position(tmy.index, latitude, longitude)

    # 2) POA irradiance via Liu-Jordan isotropic sky model.
    poa_w_m2 = _poa_isotropic(
        ghi=tmy["ghi"].to_numpy(dtype=float),
        dni=tmy["dni"].to_numpy(dtype=float),
        dhi=tmy["dhi"].to_numpy(dtype=float),
        zenith_deg=zenith_deg,
        solar_azimuth_deg=sol_az_deg,
        tilt_deg=tilt,
        surface_azimuth_deg=azimuth,
    )

    # 3) Cell temperature via NOCT model.
    temp_cell_c = _cell_temperature_noct(
        poa_w_per_m2=poa_w_m2,
        temp_air_c=tmy["temp_air"].to_numpy(dtype=float),
    )

    # 4) DC power (PVWatts equation).
    dc_w = (poa_w_m2 / 1000.0) * pdc0_w * (1.0 + GAMMA_PDC * (temp_cell_c - 25.0))
    dc_w = np.clip(dc_w, 0.0, None)

    # 5) Lumped DC-side derate.
    dc_w_after_losses = dc_w * (1.0 - system_losses_fraction)

    # 6) AC conversion. Constant efficiency, clipped at the inverter
    # nominal AC capacity (DC:AC = 1.0 in this baseline).
    ac_w = np.minimum(dc_w_after_losses * eta_inv, pdc0_w)
    ac_w = np.clip(ac_w, 0.0, None)

    ac_series = pd.Series(ac_w, index=tmy.index, name="ac_w")

    # Energy aggregations. TMY frequency is hourly, so 1 W·h = 1 W × 1 h
    # and dividing by 1 000 gives kWh.
    hourly_kwh = ac_series / 1000.0
    annual_kwh = float(hourly_kwh.sum())
    monthly_kwh = _aggregate_monthly_kwh(hourly_kwh)

    poa_annual_kwh_per_m2 = float(np.sum(poa_w_m2) / 1000.0)
    hours = len(tmy)
    capacity_factor = annual_kwh / (system_kw * hours) if hours else 0.0
    specific_yield = annual_kwh / system_kw  # kWh per kWp
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
        mean_cell_temp_c=float(np.mean(temp_cell_c)),
        ac_hourly=ac_series,
    )


def _solar_position(
    index: pd.DatetimeIndex, latitude: float, longitude: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return (solar_zenith_deg, solar_azimuth_deg) at each timestamp.

    Convention: azimuth is measured **clockwise from north**, so 180° is
    south — matching the project-wide ``surface_azimuth_deg`` convention.
    Below-horizon timestamps yield ``zenith > 90°``; the POA stage clips
    those samples to zero direct beam.

    References
    ----------
    Cooper, P. I. (1969). The absorption of radiation in solar stills.
        *Solar Energy*, 12(3), 333–346. (Declination formula.)
    Spencer, J. W. (1971). Fourier-series representation of the position
        of the sun. *Search*, 2(5), 172. (Equation of time.)
    Duffie, J. A., & Beckman, W. A. (2013). *Solar Engineering of
        Thermal Processes*, 4th ed., Wiley. Chapter 1.
    """
    # PVGIS TMY indexes are tz-aware UTC. Defensive fallback for naive.
    if index.tz is None:
        utc = pd.DatetimeIndex(index, tz="UTC")
    else:
        utc = index.tz_convert("UTC")

    n = utc.dayofyear.to_numpy(dtype=float)
    hour_utc = (
        utc.hour.to_numpy(dtype=float)
        + utc.minute.to_numpy(dtype=float) / 60.0
        + utc.second.to_numpy(dtype=float) / 3600.0
    )

    # Spencer (1971) equation of time, in minutes.
    day_angle = 2.0 * np.pi * (n - 1.0) / 365.0
    eot_min = 229.18 * (
        0.000075
        + 0.001868 * np.cos(day_angle)
        - 0.032077 * np.sin(day_angle)
        - 0.014615 * np.cos(2.0 * day_angle)
        - 0.040849 * np.sin(2.0 * day_angle)
    )

    # Cooper (1969) solar declination, in degrees.
    decl_deg = 23.45 * np.sin(np.deg2rad(360.0 * (284.0 + n) / 365.0))

    # Local apparent solar time and hour angle.
    solar_time_h = hour_utc + longitude / 15.0 + eot_min / 60.0
    omega_deg = (solar_time_h - 12.0) * 15.0

    phi = np.deg2rad(latitude)
    delta = np.deg2rad(decl_deg)
    omega = np.deg2rad(omega_deg)

    # Solar zenith (Duffie & Beckman eq. 1.6.5).
    cos_zen = (
        np.sin(phi) * np.sin(delta)
        + np.cos(phi) * np.cos(delta) * np.cos(omega)
    )
    cos_zen = np.clip(cos_zen, -1.0, 1.0)
    zenith_deg = np.rad2deg(np.arccos(cos_zen))

    # Solar azimuth (Duffie & Beckman eq. 1.6.6, written in atan2 form
    # for quadrant safety). Computed from south, then converted to the
    # project's "from north, clockwise" convention.
    sin_zen = np.sqrt(np.maximum(1.0 - cos_zen ** 2, 0.0))
    horizon_safe = sin_zen > 1e-9

    sin_az_south = np.where(
        horizon_safe, np.cos(delta) * np.sin(omega) / sin_zen, 0.0
    )
    cos_az_south = np.where(
        horizon_safe,
        (cos_zen * np.sin(phi) - np.sin(delta)) / (sin_zen * np.cos(phi) + 1e-12),
        1.0,
    )
    sin_az_south = np.clip(sin_az_south, -1.0, 1.0)
    cos_az_south = np.clip(cos_az_south, -1.0, 1.0)
    az_from_south_deg = np.rad2deg(np.arctan2(sin_az_south, cos_az_south))
    azimuth_deg = (az_from_south_deg + 180.0) % 360.0

    return zenith_deg, azimuth_deg


def _poa_isotropic(
    *,
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    zenith_deg: np.ndarray,
    solar_azimuth_deg: np.ndarray,
    tilt_deg: float,
    surface_azimuth_deg: float,
) -> np.ndarray:
    """Total plane-of-array irradiance via the isotropic sky model.

    Decomposition (W/m²):

      direct  = DNI · cos(angle of incidence)
      diffuse = DHI · (1 + cos β) / 2                 [Liu & Jordan, 1960]
      ground  = ρ · GHI · (1 - cos β) / 2

    where β is panel tilt and ρ is the ground albedo. Below-horizon
    samples receive zero direct beam.
    """
    beta = np.deg2rad(tilt_deg)
    az_diff = np.deg2rad(solar_azimuth_deg - surface_azimuth_deg)
    zen_rad = np.deg2rad(zenith_deg)

    # Angle of incidence on the tilted plane (Duffie & Beckman 1.6.2).
    cos_aoi = (
        np.cos(zen_rad) * np.cos(beta)
        + np.sin(zen_rad) * np.sin(beta) * np.cos(az_diff)
    )
    cos_aoi = np.where(zen_rad >= np.pi / 2.0, 0.0, cos_aoi)
    cos_aoi = np.clip(cos_aoi, 0.0, 1.0)

    direct = dni * cos_aoi
    diffuse = dhi * (1.0 + np.cos(beta)) / 2.0
    reflected = GROUND_ALBEDO * ghi * (1.0 - np.cos(beta)) / 2.0

    poa = direct + diffuse + reflected
    return np.clip(poa, 0.0, None)


def _cell_temperature_noct(
    *, poa_w_per_m2: np.ndarray, temp_air_c: np.ndarray
) -> np.ndarray:
    """NOCT (Nominal Operating Cell Temperature) thermal model.

    ``T_cell = T_air + (NOCT - 20) / 800 · G_poa``

    Standard for c-Si modules. Independent of wind speed (a known
    limitation; SAPM in the pvlib model captures wind explicitly). The
    deliberate divergence between the two thermal models is what the
    cross-validation is designed to probe.
    """
    return temp_air_c + (NOCT_C - 20.0) / 800.0 * poa_w_per_m2


def _aggregate_monthly_kwh(hourly_kwh: pd.Series) -> list[float]:
    """Sum hourly kWh into 12 calendar-month totals (Jan..Dec)."""
    by_month = hourly_kwh.groupby(hourly_kwh.index.month).sum()
    by_month = by_month.reindex(range(1, 13), fill_value=0.0)
    return [float(v) for v in by_month.values]
