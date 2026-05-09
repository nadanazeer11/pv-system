"""Load-profile-driven sizing endpoint.

Inverts the area-based `/api/sizing` flow: takes an appliance list,
returns a recommended system size plus the roof area it would need.
Surfaced separately so the frontend can offer a "size from my bills /
appliances" entry point alongside the existing "size from my roof" one.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.load_sizing import (
    ApplianceLibraryEntry,
    LoadSizingRequest,
    LoadSizingResult,
)
from app.services import load_sizing

router = APIRouter(prefix="/api/load-sizing", tags=["load-sizing"])


@router.get("/library", response_model=list[ApplianceLibraryEntry])
async def appliance_library() -> list[ApplianceLibraryEntry]:
    """Return the seeded Egyptian residential appliance library."""
    return load_sizing.get_appliance_library()


@router.post("", response_model=LoadSizingResult)
async def size_from_load(request: LoadSizingRequest) -> LoadSizingResult:
    """Recommend a system size from an appliance load profile."""
    try:
        return load_sizing.compute_load_sizing(request)
    except load_sizing.LoadSizingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
