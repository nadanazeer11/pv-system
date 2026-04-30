from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import energy, financial, health, sizing, tariff, weather

app = FastAPI(
    title="PV Rooftop Solar Estimator",
    description="Estimate solar PV potential and financial feasibility for Egyptian rooftops.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(weather.router)
app.include_router(sizing.router)
app.include_router(energy.router)
app.include_router(financial.router)
app.include_router(tariff.router)


@app.get("/")
async def root():
    return {
        "name": "PV Rooftop Solar Estimator",
        "version": "0.1.0",
        "docs": "/docs",
    }
