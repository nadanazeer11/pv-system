"""Tests for the PVGIS service.

Network calls are patched: we never hit the real PVGIS API in CI to keep
tests fast and offline-safe. Integration with the live API is verified
manually via /docs during development.
"""
from unittest.mock import patch

import pandas as pd
import pytest

from app.services import pvgis_service


@pytest.mark.asyncio
async def test_fetch_tmy_returns_canonical_columns(fake_tmy):
    with patch("app.services.pvgis_service.pvlib.iotools.get_pvgis_tmy") as mock_fn:
        mock_fn.return_value = (fake_tmy, None, None, None)
        df = await pvgis_service.fetch_tmy(latitude=30.0, longitude=31.2)

    assert len(df) == 8760
    assert list(df.columns) == list(pvgis_service.CANONICAL_COLUMNS)


@pytest.mark.asyncio
async def test_fetch_tmy_raises_on_missing_columns():
    bad = pd.DataFrame({"ghi": [100.0]})
    with patch("app.services.pvgis_service.pvlib.iotools.get_pvgis_tmy") as mock_fn:
        mock_fn.return_value = (bad, None, None, None)
        with pytest.raises(pvgis_service.PVGISError):
            await pvgis_service.fetch_tmy(0.0, 0.0)


@pytest.mark.asyncio
async def test_fetch_tmy_wraps_lower_level_errors():
    with patch("app.services.pvgis_service.pvlib.iotools.get_pvgis_tmy") as mock_fn:
        mock_fn.side_effect = RuntimeError("network down")
        with pytest.raises(pvgis_service.PVGISError) as info:
            await pvgis_service.fetch_tmy(0.0, 0.0)
    assert "PVGIS fetch failed" in str(info.value)


def test_summarize_irradiance_known_values(fake_tmy):
    summary = pvgis_service.summarize_irradiance(fake_tmy)

    assert summary["hours_count"] == 8760
    # 500 W/m² for 8760 hours = 4380 kWh/m² annual GHI
    assert summary["annual_ghi_kwh_per_m2"] == pytest.approx(4380.0)
    assert summary["annual_dni_kwh_per_m2"] == pytest.approx(5256.0)
    assert summary["annual_dhi_kwh_per_m2"] == pytest.approx(1752.0)
    assert summary["mean_temp_c"] == pytest.approx(25.0)
    assert summary["max_temp_c"] == pytest.approx(25.0)
    assert summary["mean_wind_m_s"] == pytest.approx(3.0)


def test_summarize_irradiance_rejects_empty():
    with pytest.raises(pvgis_service.PVGISError):
        pvgis_service.summarize_irradiance(pd.DataFrame())
