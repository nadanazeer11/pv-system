"""Energy estimation endpoints.

Exposes the pvlib (PVWatts) energy simulator as a standalone POST so the
frontend can run "what does this system produce here?" without going
through the full estimate pipeline. The full /api/estimate orchestrator
that fans out PVGIS → energy_pvlib → energy_manual → financial → CO₂
will land later in the plan; this router gives us a testable slice now.
"""
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.energy import EnergyPvlibRequest, EnergyPvlibResult
from app.services import energy_pvlib, pvgis_service

router = APIRouter(prefix="/api/energy", tags=["energy"])


@router.post("/pvlib", response_model=EnergyPvlibResult)
async def estimate_pvlib(request: EnergyPvlibRequest) -> EnergyPvlibResult:
    """Run a PVWatts simulation for the given location and system size.

    The endpoint internally fetches the TMY for the supplied lat/lon
    (PVGIS, ~5 km Egypt resolution) and runs the full pvlib chain
    documented in :mod:`app.services.energy_pvlib`.
    """
    try:
        tmy = await pvgis_service.fetch_tmy(
            request.location.latitude, request.location.longitude
        )
    except pvgis_service.PVGISError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    losses = (
        energy_pvlib.DEFAULT_SYSTEM_LOSSES_FRACTION
        if request.system_losses_fraction is None
        else request.system_losses_fraction
    )

    try:
        sim = energy_pvlib.simulate(
            tmy,
            latitude=request.location.latitude,
            longitude=request.location.longitude,
            system_kw=request.system_kw,
            tilt_deg=request.tilt_deg,
            azimuth_deg=request.azimuth_deg,
            inverter_efficiency=request.inverter_efficiency,
            system_losses_fraction=losses,
        )
    except energy_pvlib.EnergyModelError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return EnergyPvlibResult(
        annual_kwh=sim.annual_kwh,
        monthly_kwh=sim.monthly_kwh,
        specific_yield_kwh_per_kwp=sim.specific_yield_kwh_per_kwp,
        capacity_factor=sim.capacity_factor,
        performance_ratio=sim.performance_ratio,
        poa_annual_kwh_per_m2=sim.poa_annual_kwh_per_m2,
        mean_cell_temp_c=sim.mean_cell_temp_c,
        system_kw=request.system_kw,
        tilt_deg=request.tilt_deg if request.tilt_deg is not None else settings.default_tilt_deg,
        azimuth_deg=request.azimuth_deg
        if request.azimuth_deg is not None
        else settings.default_azimuth_deg,
        inverter_efficiency=request.inverter_efficiency
        if request.inverter_efficiency is not None
        else settings.inverter_efficiency,
        system_losses_fraction=losses,
    )
