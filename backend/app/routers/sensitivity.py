"""Sensitivity tornado endpoint.

Day 18 wires the OAT sensitivity kernel onto the API surface. A single
POST returns the seven swing rows the dashboard's tornado chart will
render: each row is one input parameter, swung independently between
its literature-anchored low and high while every other parameter
stays at the deterministic baseline. The rows are sorted by absolute
swing magnitude so the most influential parameter sits at the top.

The endpoint is deliberately separate from the deterministic financial
endpoint (one endpoint, one concern) and from the Day-9 Monte Carlo
endpoint, which answers the *joint* uncertainty question rather than
the OAT *attribution* question.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.sensitivity import SensitivityRequest, SensitivityResult
from app.services import sensitivity as sensitivity_service
from app.services.financial_basic import FinancialError

router = APIRouter(prefix="/api/sensitivity", tags=["sensitivity"])


@router.post("/tornado", response_model=SensitivityResult)
async def run_tornado(request: SensitivityRequest) -> SensitivityResult:
    """Run a one-at-a-time sensitivity sweep and return tornado rows.

    The deterministic core (``system_kw``, ``annual_kwh``,
    ``tariff_egp_per_kwh``) is required; every other knob is optional
    and falls back to the configured Egypt-tuned defaults. Optional
    ``ranges`` lets a methodology-aware caller override the swing band
    for any single parameter; ``parameters`` lets a caller restrict
    the sweep to a subset of inputs.
    """
    try:
        return sensitivity_service.run_sensitivity(request)
    except (sensitivity_service.SensitivityError, FinancialError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
