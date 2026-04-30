"""Weather data endpoints.

Exposes the PVGIS TMY service for ad-hoc inspection from the frontend
("show me the irradiance profile for Cairo before I commit to an estimate").
The full /api/estimate orchestration endpoint lives in app.routers.estimate
once Day 4's energy model lands.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.inputs import Location
from app.services import pvgis_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.post("/tmy")
async def get_tmy_summary(location: Location) -> dict:
    """Fetch TMY data for a location and return annual summary statistics.

    The full hourly DataFrame is intentionally not serialised over the wire
    (8,760 rows is heavy and the frontend has no use for raw irradiance).
    Use the summary fields to validate location + roughly gauge resource
    quality before running the full estimate.
    """
    try:
        tmy = await pvgis_service.fetch_tmy(location.latitude, location.longitude)
    except pvgis_service.PVGISError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "location": location.model_dump(),
        "summary": pvgis_service.summarize_irradiance(tmy),
    }
