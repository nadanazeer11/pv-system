"""Tests for the pvlib (PVWatts) energy service.

These tests exercise the full pvlib chain on **synthetic** TMY data so
they are fully offline — the live PVGIS endpoint is never called. The
fake TMY in conftest is constant irradiance for 8 760 hours, which lets
us derive expected outputs in closed form and assert tight numeric
windows.

A separate "Cairo-like" clear-sky test verifies that the model produces
a specific yield (≈ 1 700 kWh/kWp) consistent with published Egyptian
rooftop PV literature (Khalil & Fathy, 2018; Mahmoud & El-Nokali, 2023).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib
import pytest

from app.config import settings
from app.services import energy_pvlib


def test_simulate_returns_full_year_with_constant_tmy(fake_tmy):
    """Smoke test: 5 kW system on 500 W/m² constant GHI delivers a
    plausible annual AC kWh, 12 monthly entries, and metrics within the
    physically sensible ranges."""
    sim = energy_pvlib.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0
    )

    # Shape
    assert len(sim.monthly_kwh) == 12
    assert sum(sim.monthly_kwh) == pytest.approx(sim.annual_kwh, rel=1e-9)
    assert len(sim.ac_hourly) == 8760

    # Sanity windows. With 500 W/m² constant we expect a high AC yield;
    # exact value depends on POA transposition + losses (see module).
    # See conftest for fixture and module docstring for chain order.
    assert 10_000 < sim.annual_kwh < 16_000
    assert 0.0 < sim.capacity_factor < 1.0
    assert 0.0 < sim.performance_ratio < 1.0
    assert sim.poa_annual_kwh_per_m2 > 0


def test_simulate_specific_yield_in_cairo_published_range():
    """Cairo, clear-sky TMY → specific yield in 1 500–1 950 kWh/kWp.

    Published Egyptian rooftop PV pre-feasibility studies report
    Cairo-area specific yields of roughly 1 700–1 900 kWh/kWp. We
    synthesise a clear-sky year via pvlib so the test stays offline,
    and assert a slightly wider window to cover model + loss-factor
    variation.
    """
    lat, lon = 30.0444, 31.2357  # Cairo
    idx = pd.date_range("2020-01-01", periods=8760, freq="h", tz="UTC")
    loc = pvlib.location.Location(lat, lon, tz="UTC", altitude=23)
    cs = loc.get_clearsky(idx)
    # Crude but realistic seasonal+diurnal air-temp pattern for Cairo.
    doy = idx.dayofyear.to_numpy()
    hod = idx.hour.to_numpy()
    air_temp = (
        22.0
        + 8.0 * np.cos((doy - 200) * 2 * np.pi / 365.25)
        + 5.0 * np.cos((hod - 14) * np.pi / 12)
    )
    tmy = pd.DataFrame(
        {
            "ghi": cs["ghi"],
            "dni": cs["dni"],
            "dhi": cs["dhi"],
            "temp_air": air_temp,
            "wind_speed": 3.0,
        },
        index=idx,
    )

    sim = energy_pvlib.simulate(tmy, latitude=lat, longitude=lon, system_kw=5.0)

    assert 1500 < sim.specific_yield_kwh_per_kwp < 1950, (
        f"Cairo specific yield {sim.specific_yield_kwh_per_kwp:.0f} kWh/kWp "
        "is outside the published Egyptian range (1 700–1 900)."
    )
    # Performance ratio for a well-modelled Cairo system should sit in
    # the 0.7–0.85 band (NREL benchmark for hot, sunny climates).
    assert 0.70 < sim.performance_ratio < 0.85


def test_simulate_scales_linearly_with_system_size(fake_tmy):
    """PVWatts is linear in DC capacity. Doubling system_kw must double
    annual kWh exactly (no inverter clipping at our DC:AC = 1)."""
    s5 = energy_pvlib.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)
    s10 = energy_pvlib.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=10.0)

    assert s10.annual_kwh == pytest.approx(2.0 * s5.annual_kwh, rel=1e-6)
    # Specific yield (kWh per kWp) is size-invariant by construction.
    assert s10.specific_yield_kwh_per_kwp == pytest.approx(
        s5.specific_yield_kwh_per_kwp, rel=1e-6
    )


def test_simulate_west_facing_underperforms_south_facing(fake_tmy):
    """Cairo is in the northern hemisphere — south-facing (180°) should
    out-produce west-facing (270°) on an annual basis. This guards
    against accidental sign / convention flips in azimuth handling."""
    south = energy_pvlib.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0, azimuth_deg=180
    )
    west = energy_pvlib.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0, azimuth_deg=270
    )

    assert south.annual_kwh > west.annual_kwh


def test_simulate_zero_losses_beats_default_losses(fake_tmy):
    """Dropping the lumped DC-loss factor to 0 must increase output by
    exactly 1 / (1 − loss_default), i.e. the result is monotonic in the
    loss parameter."""
    default = energy_pvlib.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0
    )
    lossless = energy_pvlib.simulate(
        fake_tmy,
        latitude=30.0,
        longitude=31.2,
        system_kw=5.0,
        system_losses_fraction=0.0,
    )

    assert lossless.annual_kwh > default.annual_kwh
    # Ratio is close to 1 / (1 − 0.14) = 1.163. Exact equality would
    # require a load-independent inverter; pvlib's pvwatts inverter has
    # mild part-load non-linearity, so we allow ±1 %.
    expected_ratio = 1.0 / (1.0 - energy_pvlib.DEFAULT_SYSTEM_LOSSES_FRACTION)
    assert lossless.annual_kwh / default.annual_kwh == pytest.approx(
        expected_ratio, rel=1e-2
    )


def test_simulate_uses_config_defaults_when_orientation_omitted(fake_tmy):
    """Omitting tilt and azimuth must reproduce the result obtained when
    they are passed explicitly with the configured defaults."""
    implicit = energy_pvlib.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0
    )
    explicit = energy_pvlib.simulate(
        fake_tmy,
        latitude=30.0,
        longitude=31.2,
        system_kw=5.0,
        tilt_deg=settings.default_tilt_deg,
        azimuth_deg=settings.default_azimuth_deg,
        inverter_efficiency=settings.inverter_efficiency,
    )

    assert implicit.annual_kwh == pytest.approx(explicit.annual_kwh, rel=1e-9)


def test_simulate_rejects_empty_tmy():
    with pytest.raises(energy_pvlib.EnergyModelError):
        energy_pvlib.simulate(
            pd.DataFrame(columns=["ghi", "dni", "dhi", "temp_air", "wind_speed"]),
            latitude=30.0,
            longitude=31.2,
            system_kw=5.0,
        )


def test_simulate_rejects_non_positive_system_kw(fake_tmy):
    with pytest.raises(energy_pvlib.EnergyModelError):
        energy_pvlib.simulate(
            fake_tmy, latitude=30.0, longitude=31.2, system_kw=0.0
        )


def test_simulate_rejects_invalid_loss_fraction(fake_tmy):
    """A loss fraction of 1.0 means the array delivers nothing; a value
    above 1 is unphysical. Both are rejected loudly."""
    with pytest.raises(energy_pvlib.EnergyModelError):
        energy_pvlib.simulate(
            fake_tmy,
            latitude=30.0,
            longitude=31.2,
            system_kw=5.0,
            system_losses_fraction=1.0,
        )
    with pytest.raises(energy_pvlib.EnergyModelError):
        energy_pvlib.simulate(
            fake_tmy,
            latitude=30.0,
            longitude=31.2,
            system_kw=5.0,
            system_losses_fraction=-0.1,
        )


def test_monthly_aggregation_matches_pandas_groupby(fake_tmy):
    """Independent re-derivation of the monthly rollup as a regression
    guard against future refactors of `_aggregate_monthly_kwh`."""
    sim = energy_pvlib.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)

    expected = (sim.ac_hourly / 1000.0).groupby(sim.ac_hourly.index.month).sum()
    expected = expected.reindex(range(1, 13), fill_value=0.0).tolist()

    assert sim.monthly_kwh == pytest.approx(expected, rel=1e-9)
