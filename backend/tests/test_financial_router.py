"""Tests for the /api/financial/basic endpoint.

The financial kernel makes no network calls, so these tests are pure
HTTP-shape and error-translation checks: do the right inputs produce
200, do bad inputs produce 422, and does the response carry every
echoed assumption.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_financial_basic_endpoint_happy_path():
    response = client.post(
        "/api/financial/basic",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["capex_egp"] == 5.0 * settings.installed_cost_egp_per_kw
    assert body["annual_savings_year1_egp"] == 8000.0 * 2.0
    assert body["analysis_period_years"] == settings.analysis_period_years
    assert body["discount_rate"] == settings.discount_rate
    assert body["tariff_inflation_rate"] == settings.tariff_inflation_rate
    assert body["annual_degradation_rate"] == settings.annual_degradation_rate
    assert body["om_cost_fraction"] == settings.om_cost_fraction
    assert len(body["annual_savings_series_egp"]) == settings.analysis_period_years
    assert (
        len(body["cumulative_cashflow_series_egp"])
        == settings.analysis_period_years + 1
    )


def test_financial_basic_endpoint_honours_overrides():
    response = client.post(
        "/api/financial/basic",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
            "cost_egp_per_kw": 40000.0,
            "analysis_period_years": 20,
            "discount_rate": 0.05,
            "tariff_inflation_rate": 0.10,
            "annual_degradation_rate": 0.007,
            "om_cost_fraction": 0.015,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cost_egp_per_kw"] == 40000.0
    assert body["analysis_period_years"] == 20
    assert body["discount_rate"] == 0.05
    assert body["tariff_inflation_rate"] == 0.10
    assert body["annual_degradation_rate"] == 0.007
    assert body["om_cost_fraction"] == 0.015
    assert len(body["annual_savings_series_egp"]) == 20


def test_financial_basic_endpoint_rejects_zero_system_kw():
    """Pydantic must reject system_kw <= 0 at the schema layer."""
    response = client.post(
        "/api/financial/basic",
        json={
            "system_kw": 0.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
        },
    )
    assert response.status_code == 422


def test_financial_basic_endpoint_rejects_negative_tariff():
    response = client.post(
        "/api/financial/basic",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": -1.0,
        },
    )
    assert response.status_code == 422


def test_financial_basic_endpoint_payback_can_be_null_in_json():
    """A non-payback scenario must serialize as JSON null, not omit the field."""
    response = client.post(
        "/api/financial/basic",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 0.01,  # too low to ever recover capex
            "discount_rate": 0.0,
            "tariff_inflation_rate": 0.0,
            "annual_degradation_rate": 0.0,
            "om_cost_fraction": 0.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["simple_payback_years"] is None
    assert body["discounted_payback_years"] is None
