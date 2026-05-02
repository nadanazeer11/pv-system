"""Tests for the /api/sensitivity/tornado endpoint.

The sensitivity kernel makes no network calls, so these tests are
HTTP-shape and error-translation checks only.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_tornado_endpoint_happy_path():
    response = client.post(
        "/api/sensitivity/tornado",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "npv_egp"
    assert body["metric_at_baseline"] is not None
    assert len(body["rows"]) == 7
    # Every row carries the canonical schema shape.
    for row in body["rows"]:
        for key in (
            "parameter",
            "label",
            "baseline_value",
            "low_value",
            "high_value",
            "metric_at_low",
            "metric_at_high",
            "delta_low",
            "delta_high",
            "swing",
            "no_payback_at_low",
            "no_payback_at_high",
        ):
            assert key in row, f"row missing field: {key}"
    # And the rows are sorted by descending swing (ignoring nulls).
    swings = [row["swing"] for row in body["rows"] if row["swing"] is not None]
    assert swings == sorted(swings, reverse=True)
    # Echoed assumptions match the configured defaults.
    assert body["cost_egp_per_kw"] == settings.installed_cost_egp_per_kw
    assert body["discount_rate"] == settings.discount_rate


def test_tornado_endpoint_honours_metric_override():
    response = client.post(
        "/api/sensitivity/tornado",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
            "metric": "discounted_payback_years",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "discounted_payback_years"


def test_tornado_endpoint_honours_parameter_subset():
    response = client.post(
        "/api/sensitivity/tornado",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
            "parameters": ["annual_kwh", "cost_egp_per_kw"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 2
    assert {row["parameter"] for row in body["rows"]} == {
        "annual_kwh",
        "cost_egp_per_kw",
    }


def test_tornado_endpoint_honours_range_override():
    response = client.post(
        "/api/sensitivity/tornado",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
            "parameters": ["cost_egp_per_kw"],
            "ranges": {"cost_egp_per_kw": {"low": 20000.0, "high": 50000.0}},
        },
    )
    assert response.status_code == 200
    body = response.json()
    row = body["rows"][0]
    assert row["low_value"] == 20000.0
    assert row["high_value"] == 50000.0


def test_tornado_endpoint_rejects_zero_system_kw():
    response = client.post(
        "/api/sensitivity/tornado",
        json={"system_kw": 0.0, "annual_kwh": 8000.0, "tariff_egp_per_kwh": 2.0},
    )
    assert response.status_code == 422


def test_tornado_endpoint_rejects_low_above_high_in_range():
    response = client.post(
        "/api/sensitivity/tornado",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
            "ranges": {"cost_egp_per_kw": {"low": 50000.0, "high": 20000.0}},
        },
    )
    assert response.status_code == 422


def test_tornado_endpoint_rejects_unknown_parameter():
    """Pydantic Literal must reject parameter names outside the supported set."""
    response = client.post(
        "/api/sensitivity/tornado",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
            "parameters": ["panel_count"],
        },
    )
    assert response.status_code == 422
