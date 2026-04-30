"""PVGIS (Photovoltaic Geographical Information System) integration.

Fetches Typical Meteorological Year (TMY) hourly weather data for a given
latitude/longitude. PVGIS is operated by the European Commission Joint
Research Centre and provides peer-reviewed solar radiation data covering
Egypt at ~5 km resolution.

We use pvlib's `get_pvgis_tmy` wrapper rather than calling the HTTP endpoint
directly because:
  1. pvlib already normalises column names to its internal conventions
     (ghi, dni, dhi, temp_air, wind_speed, etc.), which our energy models
     consume directly.
  2. It handles the multiple PVGIS API formats and version negotiation.
  3. It is the same data path used in the published peer-reviewed pvlib
     literature, strengthening reproducibility for the thesis.

The actual HTTP layer is encapsulated inside pvlib; we expose an async
wrapper so the FastAPI event loop is not blocked during the request.
"""
from __future__ import annotations

import asyncio

import pandas as pd
import pvlib

from app.config import settings


class PVGISError(Exception):
    """Raised when PVGIS data fetch or parsing fails."""


# Column names we guarantee to return downstream. These match pvlib's
# internal conventions so the energy models can consume the DataFrame
# without any further renaming.
CANONICAL_COLUMNS = ("ghi", "dni", "dhi", "temp_air", "wind_speed")


def _fetch_tmy_sync(latitude: float, longitude: float) -> pd.DataFrame:
    """Synchronous PVGIS TMY fetch via pvlib.

    Returns a DataFrame indexed by hourly UTC timestamps containing the
    canonical columns used by the rest of the system.
    """
    try:
        # pvlib >= 0.11 returns (data, months_selected, inputs, metadata)
        result = pvlib.iotools.get_pvgis_tmy(
            latitude=latitude,
            longitude=longitude,
            url=settings.pvgis_base_url + "/",
            map_variables=True,
            timeout=30,
        )
    except Exception as exc:
        raise PVGISError(f"PVGIS fetch failed for ({latitude}, {longitude}): {exc}") from exc

    # pvlib returns either a tuple or DataFrame depending on version.
    data = result[0] if isinstance(result, tuple) else result

    if not isinstance(data, pd.DataFrame):
        raise PVGISError("PVGIS returned an unexpected response shape")

    missing = set(CANONICAL_COLUMNS) - set(data.columns)
    if missing:
        raise PVGISError(f"PVGIS response is missing expected columns: {missing}")

    return data[list(CANONICAL_COLUMNS)].copy()


async def fetch_tmy(latitude: float, longitude: float) -> pd.DataFrame:
    """Async PVGIS TMY fetch.

    pvlib's HTTP client is synchronous, so we run it in a worker thread to
    avoid blocking the FastAPI event loop. For the modest QPS expected from
    a thesis demo this is sufficient; an in-memory cache is added on Day 19.
    """
    return await asyncio.to_thread(_fetch_tmy_sync, latitude, longitude)


def summarize_irradiance(tmy: pd.DataFrame) -> dict:
    """Compute annual summary statistics from a TMY DataFrame.

    Returns
    -------
    dict
        annual_ghi_kwh_per_m2 : annual global horizontal energy (kWh/m²)
        annual_dni_kwh_per_m2 : annual direct normal energy (kWh/m²)
        annual_dhi_kwh_per_m2 : annual diffuse horizontal energy (kWh/m²)
        mean_temp_c           : mean ambient temperature
        max_temp_c            : maximum ambient temperature
        mean_wind_m_s         : mean wind speed at 10 m
        hours_count           : number of hourly samples (should be 8760)
    """
    if tmy.empty:
        raise PVGISError("Cannot summarise an empty TMY DataFrame")

    return {
        "annual_ghi_kwh_per_m2": float(tmy["ghi"].sum() / 1000.0),
        "annual_dni_kwh_per_m2": float(tmy["dni"].sum() / 1000.0),
        "annual_dhi_kwh_per_m2": float(tmy["dhi"].sum() / 1000.0),
        "mean_temp_c": float(tmy["temp_air"].mean()),
        "max_temp_c": float(tmy["temp_air"].max()),
        "mean_wind_m_s": float(tmy["wind_speed"].mean()),
        "hours_count": int(len(tmy)),
    }
