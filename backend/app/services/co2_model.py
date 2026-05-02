"""CO₂ avoidance kernel.

This module is the environmental-benefit half of the Day-18
deliverable. Given a year-1 PV generation figure, it computes the
year-by-year and lifetime CO₂ that the grid did *not* emit because the
PV system delivered the kWh instead. The kernel deliberately reuses
the same degradation convention as :mod:`financial_basic` so the
dashboard's energy and emissions narratives stay numerically
consistent: the kWh figure that earns EGP in the financial card and
the kWh figure that avoids kg-CO₂ in the CO₂ card are *the same*
kWh figure, year by year.

Methodological notes
--------------------
* **Why a marginal grid-average emission factor and not a true
  marginal-dispatch factor?** The Egyptian grid's marginal-dispatch
  emission factor (the kg CO₂ avoided by displacing the *next* kWh
  the grid would have generated) varies by hour, season, and merit-
  order conditions. Public, peer-reviewed Egyptian time-resolved
  marginal data is not available, so the standard practice in
  Egyptian PV pre-feasibility literature (Mahmoud & El-Nokali 2023,
  EgyptPVA 2022) is to use the EEHC published *grid-average* annual
  emission factor (0.46 kg CO₂/kWh for 2023). This biases the result
  conservatively whenever PV displaces high-merit gas peakers — the
  marginal factor is typically ~10–20 % higher than the grid-average
  in gas-dominated systems. The kernel exposes the factor as an
  override so a methodology-aware user can substitute a marginal
  number when one becomes available.

* **Why apply degradation to the energy stream and not to the
  emission factor?** Module degradation reduces *generation*; the
  grid's emission factor is determined by Egypt's electricity-mix
  policy and is the same kg/kWh whether the PV array is in year 1 or
  year 25. Applying the degradation to the energy stream and leaving
  the emission factor constant is therefore the physically correct
  decomposition.

* **Why no "embodied carbon" subtraction?** A complete LCA would net
  off the embodied carbon of the modules, inverter, and balance-of-
  system (typically 30–50 g CO₂/kWh-lifetime amortised over a 25-year
  horizon — IEA-PVPS Task 12, 2020). The thesis Limitations document
  flags this as future work; including a half-modelled LCA in the
  Day-18 headline number would over-claim precision the dataset does
  not support.

References
----------
* EEHC (Egyptian Electricity Holding Company), 2023 Annual Report —
  grid emission factor.
* Mahmoud & El-Nokali (2023). Pre-feasibility of residential rooftop
  PV in Egypt.
* US EPA Greenhouse Gas Equivalencies Calculator — Calculations and
  References (2024). Source for the equivalence constants.
* IEA-PVPS Task 12 (2020). Methodology Guidelines on Life-Cycle
  Assessment of Photovoltaic Electricity.
"""
from __future__ import annotations

from app.config import settings
from app.schemas.co2 import CO2Equivalents, CO2Request, CO2Result, CO2YearlyPoint


class CO2Error(ValueError):
    """Raised when CO₂ inputs are physically impossible.

    The Pydantic schema rejects most malformed inputs upstream; this
    error is reserved for invariants the schema cannot enforce, such
    as a non-positive analysis horizon arising from a settings reload
    that bypassed schema validation.
    """


def compute_co2_avoidance(request: CO2Request) -> CO2Result:
    """Run the full lifetime CO₂ avoidance calculation.

    Parameters
    ----------
    request : CO2Request
        Year-1 generation plus optional environmental overrides. Any
        field left as ``None`` falls back to the Egypt-tuned defaults
        in :pydata:`app.config.settings`.

    Returns
    -------
    CO2Result
        Lifetime headline numbers, the year-by-year stream, the
        cumulative trajectory, and the homeowner-friendly equivalences,
        plus every assumption echoed back for self-auditing.

    Raises
    ------
    CO2Error
        If the resolved analysis period is non-positive — defended
        here so the service is safe to import standalone.
    """
    analysis_years = (
        request.analysis_period_years
        if request.analysis_period_years is not None
        else settings.analysis_period_years
    )
    degradation = (
        request.annual_degradation_rate
        if request.annual_degradation_rate is not None
        else settings.annual_degradation_rate
    )
    emission_factor = (
        request.grid_emission_factor_kg_per_kwh
        if request.grid_emission_factor_kg_per_kwh is not None
        else settings.egypt_grid_emission_kg_per_kwh
    )

    if analysis_years < 1:
        raise CO2Error("analysis_period_years must be at least 1")

    annual_series: list[CO2YearlyPoint] = []
    cumulative_kg: list[float] = [0.0]
    running = 0.0

    for year in range(1, analysis_years + 1):
        gen_t = request.annual_kwh * (1.0 - degradation) ** (year - 1)
        co2_t = gen_t * emission_factor
        running += co2_t
        annual_series.append(
            CO2YearlyPoint(year=year, generation_kwh=gen_t, co2_avoided_kg=co2_t)
        )
        cumulative_kg.append(running)

    lifetime_kg = running
    lifetime_tonnes = lifetime_kg / 1000.0
    year1_kg = annual_series[0].co2_avoided_kg

    equivalents = _compute_equivalents(
        lifetime_co2_kg=lifetime_kg, analysis_years=analysis_years
    )

    return CO2Result(
        annual_co2_avoided_year1_kg=year1_kg,
        lifetime_co2_avoided_kg=lifetime_kg,
        lifetime_co2_avoided_tonnes=lifetime_tonnes,
        annual_series=annual_series,
        cumulative_co2_avoided_kg=cumulative_kg,
        equivalents=equivalents,
        annual_kwh=request.annual_kwh,
        analysis_period_years=analysis_years,
        annual_degradation_rate=degradation,
        grid_emission_factor_kg_per_kwh=emission_factor,
    )


def _compute_equivalents(
    *, lifetime_co2_kg: float, analysis_years: int
) -> CO2Equivalents:
    """Translate a lifetime kg-CO₂ figure into homeowner-friendly units.

    The car and petrol equivalents are direct ratios — one constant kg
    CO₂ per km / per litre, applied to the lifetime total. The "trees"
    equivalent is normalised by the analysis horizon: the question is
    "how many trees would have absorbed *this much* CO₂ *over the same
    time window*?", so the per-tree-per-year rate is multiplied by the
    horizon to give the per-tree absorption *across the same horizon*,
    and the lifetime CO₂ is divided by that.
    """
    car_km = (
        lifetime_co2_kg / settings.co2_kg_per_passenger_car_km
        if settings.co2_kg_per_passenger_car_km > 0
        else 0.0
    )
    petrol_l = (
        lifetime_co2_kg / settings.co2_kg_per_petrol_litre
        if settings.co2_kg_per_petrol_litre > 0
        else 0.0
    )
    tree_horizon_kg = settings.co2_kg_per_tree_grown_year * analysis_years
    trees = lifetime_co2_kg / tree_horizon_kg if tree_horizon_kg > 0 else 0.0

    return CO2Equivalents(
        equivalent_passenger_car_km=car_km,
        equivalent_petrol_litres=petrol_l,
        equivalent_urban_trees_grown=trees,
    )
