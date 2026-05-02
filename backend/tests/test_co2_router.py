"""Tests for the /api/co2/avoided endpoint.

The CO₂ kernel makes no network calls, so these tests are HTTP-shape
and error-translation checks: do the right inputs produce 200, do bad
inputs produce 422, and does the response carry every echoed
assumption.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_co2_endpoint_happy_path():
    response = client.post("/api/co2/avoided", json={"annual_kwh": 8000.0})

    assert response.status_code == 200
    body = response.json()
    assert body["annual_co2_avoided_year1_kg"] == 8000.0 * settings.egypt_grid_emission_kg_per_kwh
    assert body["analysis_period_years"] == settings.analysis_period_years
    assert (
        body["grid_emission_factor_kg_per_kwh"]
        == settings.egypt_grid_emission_kg_per_kwh
    )
    assert body["annual_degradation_rate"] == settings.annual_degradation_rate
    assert len(body["annual_series"]) == settings.analysis_period_years
    assert (
        len(body["cumulative_co2_avoided_kg"])
        == settings.analysis_period_years + 1
    )
    assert body["cumulative_co2_avoided_kg"][0] == 0.0
    assert body["lifetime_co2_avoided_tonnes"] > 0
    assert body["equivalents"]["equivalent_passenger_car_km"] > 0


def test_co2_endpoint_honours_overrides():
    response = client.post(
        "/api/co2/avoided",
        json={
            "annual_kwh": 6000.0,
            "analysis_period_years": 20,
            "annual_degradation_rate": 0.008,
            "grid_emission_factor_kg_per_kwh": 0.40,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_period_years"] == 20
    assert body["annual_degradation_rate"] == 0.008
    assert body["grid_emission_factor_kg_per_kwh"] == 0.40
    assert len(body["annual_series"]) == 20
    assert body["annual_co2_avoided_year1_kg"] == 6000.0 * 0.40


def test_co2_endpoint_rejects_zero_kwh():
    response = client.post("/api/co2/avoided", json={"annual_kwh": 0.0})
    assert response.status_code == 422


def test_co2_endpoint_rejects_negative_emission_factor():
    response = client.post(
        "/api/co2/avoided",
        json={"annual_kwh": 8000.0, "grid_emission_factor_kg_per_kwh": -0.1},
    )
    assert response.status_code == 422
