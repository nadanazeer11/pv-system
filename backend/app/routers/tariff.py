"""EgyptERA tiered-tariff endpoints.

Day 8 — Contribution B. Three sibling routes share one router so the
frontend can keep its tariff section logically grouped:

* ``/api/tariff/bill``     — compute a household's bill from a 12-month
                              consumption profile.
* ``/api/tariff/savings``  — compute the bill *with* PV netting and
                              report tier-aware savings.
* ``/api/tariff/optimize`` — sweep system sizes and return the kW that
                              maximises lifetime NPV.

Why a dedicated router rather than appending to ``/api/financial``?
The financial router handles flat-tariff economics; the tariff router
encapsulates Egypt-specific structure. Keeping them separate keeps the
flat-tariff baseline available as a counterfactual (used by Day 18's
sensitivity tornado) and matches the thesis's narrative split between
"baseline" and "contributions".
"""
from fastapi import APIRouter, HTTPException

from app.schemas.tariff import (
    TariffBillRequest,
    TariffBillResult,
    TariffOptimizeRequest,
    TariffOptimizeResult,
    TariffSavingsRequest,
    TariffSavingsResult,
)
from app.services import tiered_tariff

router = APIRouter(prefix="/api/tariff", tags=["tariff"])


@router.post("/bill", response_model=TariffBillResult)
async def compute_bill(request: TariffBillRequest) -> TariffBillResult:
    """Compute a household's annual bill under a tiered residential tariff."""
    try:
        return tiered_tariff.compute_bill(request)
    except tiered_tariff.TariffError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/savings", response_model=TariffSavingsResult)
async def compute_savings(request: TariffSavingsRequest) -> TariffSavingsResult:
    """Compute tier-aware savings from netting PV generation against consumption."""
    try:
        return tiered_tariff.compute_savings(request)
    except tiered_tariff.TariffError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/optimize", response_model=TariffOptimizeResult)
async def optimize_size(request: TariffOptimizeRequest) -> TariffOptimizeResult:
    """Find the system size that maximises lifetime NPV under the tiered schedule."""
    try:
        return tiered_tariff.optimize_system_size(request)
    except tiered_tariff.TariffError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
