from pydantic import BaseModel


class SystemSize(BaseModel):
    panel_count: int
    system_kw: float
    usable_roof_area_m2: float


class EnergyResult(BaseModel):
    annual_kwh: float
    monthly_kwh: list[float]  # 12 entries Jan..Dec


class FinancialResult(BaseModel):
    installation_cost_egp: float
    annual_savings_egp: float
    simple_payback_years: float


class CO2Result(BaseModel):
    annual_kg_co2_avoided: float


class EstimateResponse(BaseModel):
    system: SystemSize
    energy_pvlib: EnergyResult
    energy_manual: EnergyResult
    financial: FinancialResult
    co2: CO2Result
