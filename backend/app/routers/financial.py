"""Financial feasibility endpoints.

Day 6 exposes the *flat-tariff* basic financial kernel as a standalone
POST so the frontend can render a payback card the moment an annual
generation figure is available — without waiting for tier optimisation
(Day 8) or Monte Carlo (Day 9). Those later services will live behind
sibling routes on this same router.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.financial import FinancialBasicRequest, FinancialBasicResult
from app.services import financial_basic

router = APIRouter(prefix="/api/financial", tags=["financial"])


@router.post("/basic", response_model=FinancialBasicResult)
async def compute_basic_financials(
    request: FinancialBasicRequest,
) -> FinancialBasicResult:
    """Compute capex, payback, NPV, and LCOE for a given system + tariff.

    Inputs ``system_kw`` and ``annual_kwh`` are typically taken from the
    output of either :http:post:`/api/energy/pvlib` or
    :http:post:`/api/energy/manual`. The flat tariff supplied here will
    be replaced by the Egyptian tiered model once Day 8 lands.
    """
    try:
        model = financial_basic.compute_financials(request)
    except financial_basic.FinancialError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return financial_basic.to_result(model)
