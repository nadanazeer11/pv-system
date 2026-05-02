"""CO₂ avoidance endpoint.

Day 18 wires the environmental-benefit kernel onto the API surface.
A single POST returns the lifetime CO₂ avoided plus three EPA-style
equivalences and the year-by-year cumulative trajectory the dashboard
will draw alongside the financial cumulative cash-flow chart.

The endpoint is intentionally separate from the financial endpoints so
the frontend can render the CO₂ card the moment a year-1 generation
figure is available — without waiting for the tariff or Monte Carlo
calls.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.co2 import CO2Request, CO2Result
from app.services import co2_model

router = APIRouter(prefix="/api/co2", tags=["co2"])


@router.post("/avoided", response_model=CO2Result)
async def compute_co2_avoided(request: CO2Request) -> CO2Result:
    """Compute lifetime CO₂ avoidance and homeowner-friendly equivalences.

    The required input ``annual_kwh`` is typically taken from the output
    of either :http:post:`/api/energy/pvlib` or
    :http:post:`/api/energy/manual`. Optional overrides let a caller
    substitute a true marginal-dispatch emission factor when one is
    available; the default is the EEHC published Egyptian grid-average
    figure for 2023.
    """
    try:
        return co2_model.compute_co2_avoidance(request)
    except co2_model.CO2Error as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
