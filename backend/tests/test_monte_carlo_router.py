"""HTTP-shape tests for the Monte Carlo endpoint.

The kernel itself is covered by :mod:`test_monte_carlo`; these tests
verify only the FastAPI surface — that the schema rejects malformed
distributions with 422, that the happy path returns the full result
shape, and that ``random_seed`` round-trips through the JSON layer
without any precision loss.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _baseline_payload(**overrides) -> dict:
    body = {
        "system_kw": 5.0,
        "annual_kwh": 8000.0,
        "tariff_egp_per_kwh": 2.0,
        "n_simulations": 200,
        "random_seed": 42,
    }
    body.update(overrides)
    return body


def test_run_endpoint_happy_path():
    response = client.post("/api/monte-carlo/run", json=_baseline_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["n_simulations"] == 200
    for key in (
        "payback_years",
        "npv_egp",
        "lcoe_egp_per_kwh",
        "lifetime_savings_egp",
    ):
        bucket = body[key]
        for pct in ("p05", "p10", "p25", "p50", "p75", "p90", "p95", "mean", "std"):
            assert pct in bucket
    assert "payback_histogram" in body
    assert "npv_histogram" in body
    assert 0.0 <= body["payback_probability"] <= 1.0
    assert 0.0 <= body["positive_npv_probability"] <= 1.0


def test_seed_makes_response_deterministic_over_http():
    a = client.post("/api/monte-carlo/run", json=_baseline_payload(random_seed=99))
    b = client.post("/api/monte-carlo/run", json=_baseline_payload(random_seed=99))
    assert a.status_code == b.status_code == 200
    assert a.json()["npv_egp"]["p50"] == b.json()["npv_egp"]["p50"]


def test_rejects_zero_system_kw():
    response = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(system_kw=0.0),
    )
    assert response.status_code == 422


def test_rejects_zero_annual_kwh():
    response = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(annual_kwh=0.0),
    )
    assert response.status_code == 422


def test_rejects_simulation_count_below_floor():
    response = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(n_simulations=5),
    )
    assert response.status_code == 422


def test_rejects_simulation_count_above_ceiling():
    response = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(n_simulations=999_999),
    )
    assert response.status_code == 422


def test_rejects_malformed_normal_distribution():
    """A normal distribution missing ``std`` is malformed and must
    surface as 422 at the schema layer rather than silently sampling
    constants."""
    response = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(
            tariff_inflation_rate_dist={"kind": "normal", "mean": 0.08},
        ),
    )
    assert response.status_code == 422


def test_rejects_inverted_triangular_bounds():
    response = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(
            degradation_rate_dist={
                "kind": "triangular",
                "low": 0.05,
                "mode": 0.06,
                "high": 0.001,
            },
        ),
    )
    assert response.status_code == 422


def test_explicit_distribution_overrides_round_trip():
    """A custom distribution payload must reach the kernel — verified
    via its effect on the result rather than by inspecting internals."""
    narrow = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(
            tariff_inflation_rate_dist={
                "kind": "normal",
                "mean": 0.08,
                "std": 0.001,
                "clip_min": 0.0,
            },
        ),
    ).json()
    wide = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(
            tariff_inflation_rate_dist={
                "kind": "normal",
                "mean": 0.08,
                "std": 0.05,
                "clip_min": 0.0,
            },
        ),
    ).json()
    assert wide["npv_egp"]["std"] > narrow["npv_egp"]["std"]


def test_histogram_payload_is_well_formed():
    body = client.post("/api/monte-carlo/run", json=_baseline_payload()).json()
    for hist_key in ("payback_histogram", "npv_histogram"):
        hist = body[hist_key]
        assert len(hist["bin_edges"]) == len(hist["counts"]) + 1
        assert all(b > a for a, b in zip(hist["bin_edges"], hist["bin_edges"][1:]))


def test_response_echoes_random_seed():
    body = client.post(
        "/api/monte-carlo/run",
        json=_baseline_payload(random_seed=2026),
    ).json()
    assert body["random_seed"] == 2026


def test_missing_seed_renders_as_null():
    body = client.post(
        "/api/monte-carlo/run",
        json={
            "system_kw": 5.0,
            "annual_kwh": 8000.0,
            "tariff_egp_per_kwh": 2.0,
            "n_simulations": 100,
        },
    ).json()
    assert body["random_seed"] is None
