"""Monte Carlo uncertainty endpoint.

Day 9 wires Contribution C onto the API surface. A single POST runs the
ensemble simulation and returns percentile bands plus probability of
payback / positive NPV — the inputs the Day 14 dashboard's "payback
with confidence interval" card and Day 16's fan chart will consume.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.monte_carlo import MonteCarloRequest, MonteCarloResult
from app.services import monte_carlo as monte_carlo_service

router = APIRouter(prefix="/api/monte-carlo", tags=["monte-carlo"])


@router.post("/run", response_model=MonteCarloResult)
async def run_monte_carlo(request: MonteCarloRequest) -> MonteCarloResult:
    """Run the Monte Carlo simulation for a given system configuration.

    The deterministic core (system size, year-1 generation, base
    tariff) is required; every uncertain parameter has an Egypt-tuned
    default distribution which the caller may override. Pass a
    ``random_seed`` to make the response reproducible.
    """
    try:
        return monte_carlo_service.run_monte_carlo(request)
    except monte_carlo_service.MonteCarloError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
