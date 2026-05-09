"""Shading-geometry endpoint.

Day-19 deliverable A: exposes the inter-row spacing kernel under
``POST /api/shading/inter-row``. Subsequent deliverables (obstacle
shadow sweep, horizon obstruction) will live alongside this one under
the same ``/api/shading`` prefix.
"""
from fastapi import APIRouter

from app.schemas.shading import InterRowSpacingRequest, InterRowSpacingResult
from app.services import shading

router = APIRouter(prefix="/api/shading", tags=["shading"])


@router.post("/inter-row", response_model=InterRowSpacingResult)
async def inter_row_spacing(request: InterRowSpacingRequest) -> InterRowSpacingResult:
    """Compute row pitch + density factor for a tilted panel array."""
    return shading.compute_inter_row_spacing(request)
