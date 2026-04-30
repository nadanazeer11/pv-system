"""Tests for the manual physics-based energy service.

These tests exercise the from-first-principles chain on **synthetic**
TMY data so they are fully offline. A separate Cairo clear-sky test
verifies that the manual model produces a specific yield consistent
with the published Egyptian rooftop PV literature, and a
cross-validation test asserts the manual model agrees with the pvlib
model to within the order-of-magnitude tolerance expected of two
different sky-diffuse and cell-temp models.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib
import pytest

from app.config import settings
from app.services import energy_manual, energy_pvlib


def _cairo_clearsky_tmy() -> pd.DataFrame:
    """Synthetic Cairo clear-sky TMY using pvlib's clear-sky engine.

    Identical recipe to the pvlib test suite so any cross-validation
    delta is attributable to the model, not the input data.
    """
    lat, lon = 30.0444, 31.2357
    idx = pd.date_range("2020-01-01", periods=8760, freq="h", tz="UTC")
    loc = pvlib.location.Location(lat, lon, tz="UTC", altitude=23)
    cs = loc.get_clearsky(idx)
    doy = idx.dayofyear.to_numpy()
    hod = idx.hour.to_numpy()
    air_temp = (
        22.0
        + 8.0 * np.cos((doy - 200) * 2 * np.pi / 365.25)
        + 5.0 * np.cos((hod - 14) * np.pi / 12)
    )
    return pd.DataFrame(
        {
            "ghi": cs["ghi"],
            "dni": cs["dni"],
            "dhi": cs["dhi"],
            "temp_air": air_temp,
            "wind_speed": 3.0,
        },
        index=idx,
    )


def test_simulate_returns_full_year_with_constant_tmy(fake_tmy):
    """Smoke test: 5 kW system, fake constant TMY, manual chain runs
    end-to-end and produces a plausible annual AC kWh and 12 monthly
    entries. Annual range is wider than the pvlib test because the
    isotropic sky model under-counts diffuse on tilted planes for
    low-zenith hours and the NOCT thermal model is wind-independent."""
    sim = energy_manual.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0
    )

    assert len(sim.monthly_kwh) == 12
    assert sum(sim.monthly_kwh) == pytest.approx(sim.annual_kwh, rel=1e-9)
    assert len(sim.ac_hourly) == 8760

    assert 6_000 < sim.annual_kwh < 18_000
    assert 0.0 < sim.capacity_factor < 1.0
    assert 0.0 < sim.performance_ratio < 1.0
    assert sim.poa_annual_kwh_per_m2 > 0


def test_simulate_specific_yield_in_cairo_published_range():
    """Cairo clear-sky TMY → specific yield in the 1 500–1 950 kWh/kWp
    band reported by Egyptian rooftop PV pre-feasibility studies. The
    isotropic sky model is slightly conservative versus Hay-Davies, so
    the lower edge is widened to 1 500 to absorb that systematic
    difference."""
    tmy = _cairo_clearsky_tmy()
    sim = energy_manual.simulate(
        tmy, latitude=30.0444, longitude=31.2357, system_kw=5.0
    )

    assert 1500 < sim.specific_yield_kwh_per_kwp < 1950, (
        f"Cairo manual specific yield {sim.specific_yield_kwh_per_kwp:.0f} "
        "kWh/kWp is outside the published Egyptian range (≈1 700–1 900)."
    )
    assert 0.65 < sim.performance_ratio < 0.85


def test_manual_and_pvlib_agree_within_band_on_cairo():
    """The two independent chains should land within ~15 % of each
    other on the same Cairo TMY. Larger gaps would point at a bug in
    one of them; smaller gaps would render the cross-validation
    chapter uninteresting. This is the headline thesis assertion: the
    dual-energy backbone is internally consistent."""
    tmy = _cairo_clearsky_tmy()
    pv = energy_pvlib.simulate(tmy, latitude=30.0444, longitude=31.2357, system_kw=5.0)
    mn = energy_manual.simulate(tmy, latitude=30.0444, longitude=31.2357, system_kw=5.0)

    relative_delta = abs(pv.annual_kwh - mn.annual_kwh) / pv.annual_kwh
    assert relative_delta < 0.15, (
        f"manual and pvlib annual kWh differ by {relative_delta:.1%} "
        f"(pvlib={pv.annual_kwh:.0f}, manual={mn.annual_kwh:.0f}); "
        "expected agreement within 15 %."
    )


def test_simulate_scales_linearly_with_system_size(fake_tmy):
    """The PVWatts-style equation is linear in DC capacity; doubling
    the system must double the annual output exactly (no clipping at
    DC:AC = 1)."""
    s5 = energy_manual.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0)
    s10 = energy_manual.simulate(fake_tmy, latitude=30.0, longitude=31.2, system_kw=10.0)

    assert s10.annual_kwh == pytest.approx(2.0 * s5.annual_kwh, rel=1e-9)
    assert s10.specific_yield_kwh_per_kwp == pytest.approx(
        s5.specific_yield_kwh_per_kwp, rel=1e-9
    )


def test_simulate_west_facing_underperforms_south_facing():
    """South-facing > west-facing on annual production for a Cairo
    site. Uses a Cairo clear-sky TMY because the constant fake_tmy
    fixture pairs constant DNI with a moving sun, which does still
    produce the right ordering but is less convincing than a real
    diurnal pattern. Guards against accidental azimuth-convention
    flips in :func:`_solar_position`."""
    tmy = _cairo_clearsky_tmy()
    south = energy_manual.simulate(
        tmy, latitude=30.0444, longitude=31.2357, system_kw=5.0, azimuth_deg=180
    )
    west = energy_manual.simulate(
        tmy, latitude=30.0444, longitude=31.2357, system_kw=5.0, azimuth_deg=270
    )

    assert south.annual_kwh > west.annual_kwh


def test_simulate_zero_losses_beats_default_losses(fake_tmy):
    """Output is monotonic in the loss factor; zero losses raises
    output by exactly 1 / (1 − loss_default)."""
    default = energy_manual.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0
    )
    lossless = energy_manual.simulate(
        fake_tmy,
        latitude=30.0,
        longitude=31.2,
        system_kw=5.0,
        system_losses_fraction=0.0,
    )

    assert lossless.annual_kwh > default.annual_kwh
    expected_ratio = 1.0 / (1.0 - energy_manual.DEFAULT_SYSTEM_LOSSES_FRACTION)
    assert lossless.annual_kwh / default.annual_kwh == pytest.approx(
        expected_ratio, rel=1e-6
    )


def test_simulate_uses_config_defaults_when_orientation_omitted(fake_tmy):
    """Omitting tilt and azimuth must reproduce the result obtained
    when they are passed explicitly with the configured defaults."""
    implicit = energy_manual.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0
    )
    explicit = energy_manual.simulate(
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
    with pytest.raises(energy_manual.EnergyModelError):
        energy_manual.simulate(
            pd.DataFrame(columns=["ghi", "dni", "dhi", "temp_air", "wind_speed"]),
            latitude=30.0,
            longitude=31.2,
            system_kw=5.0,
        )


def test_simulate_rejects_non_positive_system_kw(fake_tmy):
    with pytest.raises(energy_manual.EnergyModelError):
        energy_manual.simulate(
            fake_tmy, latitude=30.0, longitude=31.2, system_kw=0.0
        )


def test_simulate_rejects_invalid_loss_fraction(fake_tmy):
    """Loss = 1.0 is a system that delivers nothing; > 1 is unphysical.
    Both must raise."""
    with pytest.raises(energy_manual.EnergyModelError):
        energy_manual.simulate(
            fake_tmy,
            latitude=30.0,
            longitude=31.2,
            system_kw=5.0,
            system_losses_fraction=1.0,
        )
    with pytest.raises(energy_manual.EnergyModelError):
        energy_manual.simulate(
            fake_tmy,
            latitude=30.0,
            longitude=31.2,
            system_kw=5.0,
            system_losses_fraction=-0.1,
        )


def test_solar_position_at_cairo_solar_noon_summer():
    """Sanity-check the solar geometry against textbook values.

    On the summer solstice (June 21) at Cairo (φ = 30.04°), solar noon
    elevation is 90° − (φ − δ) ≈ 83.4° → zenith ≈ 6.6°. We pick a UTC
    timestamp close to local solar noon and confirm both the zenith
    band and the south-pointing azimuth (≈ 180°) — this is a directly
    verifiable hand calculation a thesis reviewer can redo in 30 s.
    """
    # Cairo longitude ≈ 31.24° → solar noon at UTC ≈ 12 - 31.24/15 ≈ 9.92 h
    # (ignoring the ±~2 min equation of time on June 21).
    idx = pd.DatetimeIndex(["2020-06-21T09:55:00"], tz="UTC")
    zenith, azimuth = energy_manual._solar_position(idx, 30.0444, 31.2357)

    assert 0.0 <= zenith[0] < 12.0  # near-overhead at solar noon
    assert 150.0 < azimuth[0] < 210.0  # south-ish


def test_monthly_aggregation_matches_pandas_groupby(fake_tmy):
    """Independent re-derivation of the monthly rollup as a regression
    guard against future refactors of `_aggregate_monthly_kwh`."""
    sim = energy_manual.simulate(
        fake_tmy, latitude=30.0, longitude=31.2, system_kw=5.0
    )

    expected = (sim.ac_hourly / 1000.0).groupby(sim.ac_hourly.index.month).sum()
    expected = expected.reindex(range(1, 13), fill_value=0.0).tolist()

    assert sim.monthly_kwh == pytest.approx(expected, rel=1e-9)
