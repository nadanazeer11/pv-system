"""Tests for the /api/shading/inter-row endpoint."""
import math

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_inter_row_with_empty_body_uses_defaults():
    """An empty body must compute the project-default geometry."""
    response = client.post("/api/shading/inter-row", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["panel_slope_height_m"] == 1.8
    assert body["tilt_deg"] == 26.0
    assert body["sun_elevation_deg"] == 22.0
    assert body["row_pitch_m"] == round(
        body["panel_footprint_m"] + body["shadow_length_m"], 12,
    ) or abs(
        body["row_pitch_m"] - body["panel_footprint_m"] - body["shadow_length_m"]
    ) < 1e-6


def test_inter_row_with_overrides():
    response = client.post(
        "/api/shading/inter-row",
        json={
            "panel_slope_height_m": 2.0,
            "tilt_deg": 30,
            "sun_elevation_deg": 30,
        },
    )
    assert response.status_code == 200
    body = response.json()
    expected_footprint = 2.0 * math.cos(math.radians(30))
    assert body["panel_footprint_m"] == round(expected_footprint, 12) or abs(
        body["panel_footprint_m"] - expected_footprint
    ) < 1e-9
    assert body["panel_slope_height_m"] == 2.0
    assert body["tilt_deg"] == 30


def test_inter_row_flat_panels_returns_unit_density():
    response = client.post("/api/shading/inter-row", json={"tilt_deg": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["inter_row_density_factor"] == 1.0
    assert body["shadow_length_m"] == 0.0


def test_inter_row_rejects_out_of_range_tilt():
    response = client.post("/api/shading/inter-row", json={"tilt_deg": 95})
    assert response.status_code == 422


def test_inter_row_rejects_zero_sun_elevation():
    """Sun on the horizon → infinite shadow → must be rejected at schema layer."""
    response = client.post("/api/shading/inter-row", json={"sun_elevation_deg": 0})
    assert response.status_code == 422


def test_inter_row_rejects_negative_panel_height():
    response = client.post(
        "/api/shading/inter-row", json={"panel_slope_height_m": -1},
    )
    assert response.status_code == 422
