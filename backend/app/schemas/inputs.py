from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Decimal degrees")


class EstimateRequest(BaseModel):
    location: Location
    roof_area_m2: float = Field(..., gt=0, description="Total roof area in square metres")
    tilt_deg: float | None = Field(None, ge=0, le=90, description="Panel tilt angle (defaults to local optimum if omitted)")
    azimuth_deg: float | None = Field(None, ge=0, le=360, description="Panel azimuth (defaults to 180° south)")
    tariff_egp_per_kwh: float = Field(..., gt=0, description="Flat tariff fallback if tier data unavailable")
    monthly_consumption_kwh: float | None = Field(None, gt=0, description="Average monthly consumption — required for tiered tariff optimization")
