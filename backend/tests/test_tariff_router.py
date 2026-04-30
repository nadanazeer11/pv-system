"""HTTP-shape tests for the tiered-tariff endpoints.

The kernel itself is exercised by ``test_tiered_tariff.py``; these
tests verify only the HTTP surface — does the right request produce
200, do bad requests produce 422, and does the response carry every
expected field.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _flat(monthly_kwh: float) -> list[float]:
    return [monthly_kwh] * 12


def _baseline_generation() -> list[float]:
    pattern = [
        500.0,
        550.0,
        650.0,
        700.0,
        780.0,
        820.0,
        850.0,
        820.0,
        750.0,
        680.0,
        550.0,
        500.0,
    ]
    total = sum(pattern)
    return [v * (8000.0 / total) for v in pattern]


# ───────────────────────────── /bill ──────────────────────────────────


def test_bill_endpoint_happy_path():
    response = client.post(
        "/api/tariff/bill",
        json={"monthly_consumption_kwh": _flat(200.0)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["annual_consumption_kwh"] == 12 * 200.0
    # 200 kWh under EgyptERA: 50·0.58 + 50·0.68 + 100·0.83 = 146 EGP/month
    assert body["annual_bill_egp"] == 12 * 146.0
    assert len(body["monthly_breakdown"]) == 12
    assert len(body["tiers"]) >= 1


def test_bill_endpoint_rejects_eleven_months():
    response = client.post(
        "/api/tariff/bill",
        json={"monthly_consumption_kwh": [100.0] * 11},
    )
    assert response.status_code == 422


def test_bill_endpoint_rejects_negative_kwh():
    response = client.post(
        "/api/tariff/bill",
        json={"monthly_consumption_kwh": [100.0] * 11 + [-10.0]},
    )
    assert response.status_code == 422


def test_bill_endpoint_accepts_tier_override():
    response = client.post(
        "/api/tariff/bill",
        json={
            "monthly_consumption_kwh": _flat(50.0),
            "tiers": [
                {"upper_kwh_per_month": 100.0, "egp_per_kwh": 1.0},
                {"upper_kwh_per_month": 1.0e9, "egp_per_kwh": 2.0},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["annual_bill_egp"] == 12 * 50.0


# ─────────────────────────── /savings ─────────────────────────────────


def test_savings_endpoint_happy_path():
    response = client.post(
        "/api/tariff/savings",
        json={
            "monthly_consumption_kwh": _flat(500.0),
            "monthly_generation_kwh": _flat(300.0),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bill_after_egp"] < body["bill_before_egp"]
    assert body["annual_savings_egp"] > 0.0
    assert len(body["monthly_bill_before"]) == 12
    assert len(body["monthly_bill_after"]) == 12


def test_savings_endpoint_rejects_mismatched_lengths():
    response = client.post(
        "/api/tariff/savings",
        json={
            "monthly_consumption_kwh": _flat(500.0),
            "monthly_generation_kwh": [100.0] * 11,
        },
    )
    assert response.status_code == 422


def test_savings_endpoint_export_credit_increases_savings():
    base = client.post(
        "/api/tariff/savings",
        json={
            "monthly_consumption_kwh": _flat(50.0),
            "monthly_generation_kwh": _flat(80.0),
        },
    ).json()
    with_export = client.post(
        "/api/tariff/savings",
        json={
            "monthly_consumption_kwh": _flat(50.0),
            "monthly_generation_kwh": _flat(80.0),
            "export_credit_egp_per_kwh": 0.5,
        },
    ).json()
    assert with_export["annual_savings_egp"] > base["annual_savings_egp"]


# ────────────────────────── /optimize ─────────────────────────────────


def test_optimize_endpoint_happy_path():
    response = client.post(
        "/api/tariff/optimize",
        json={
            "monthly_consumption_kwh": _flat(600.0),
            "baseline_monthly_generation_kwh": _baseline_generation(),
            "baseline_system_kw": 5.0,
            "max_system_kw": 10.0,
            "grid_step_kw": 0.5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["optimal_system_kw"] >= 0.0
    assert "candidates" in body
    assert len(body["candidates"]) >= 2
    assert body["analysis_period_years"] >= 1


def test_optimize_endpoint_rejects_zero_max_kw():
    response = client.post(
        "/api/tariff/optimize",
        json={
            "monthly_consumption_kwh": _flat(600.0),
            "baseline_monthly_generation_kwh": _baseline_generation(),
            "baseline_system_kw": 5.0,
            "max_system_kw": 0.0,
            "grid_step_kw": 0.5,
        },
    )
    assert response.status_code == 422


def test_optimize_endpoint_rejects_zero_baseline_kw():
    response = client.post(
        "/api/tariff/optimize",
        json={
            "monthly_consumption_kwh": _flat(600.0),
            "baseline_monthly_generation_kwh": _baseline_generation(),
            "baseline_system_kw": 0.0,
            "max_system_kw": 10.0,
            "grid_step_kw": 0.5,
        },
    )
    assert response.status_code == 422


def test_optimize_endpoint_returns_flat_tariff_counterfactual():
    response = client.post(
        "/api/tariff/optimize",
        json={
            "monthly_consumption_kwh": _flat(600.0),
            "baseline_monthly_generation_kwh": _baseline_generation(),
            "baseline_system_kw": 5.0,
            "max_system_kw": 15.0,
            "grid_step_kw": 0.5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "flat_tariff_optimum_kw" in body
    assert body["flat_tariff_optimum_kw"] >= body["optimal_system_kw"] - 1e-6
