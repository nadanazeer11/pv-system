"""PV sizing endpoint.

Exposes the sizing service so the frontend can show "you can fit N
panels (X kW) on this roof" before the user commits to running the
full estimate pipeline. Kept separate from /api/estimate so it can be
called cheaply on every roof-area edit.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.sizing import SizingRequest, SizingResult
from app.services import pv_sizing

router = APIRouter(prefix="/api/sizing", tags=["sizing"])


@router.post("", response_model=SizingResult)
async def size_system(request: SizingRequest) -> SizingResult:
    """Compute panel count and DC capacity for a given roof area."""
    try:
        return pv_sizing.compute_system_size(request)
    except pv_sizing.SizingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
