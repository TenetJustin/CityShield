from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app import paradise_forecast
from backend.app.main import app


client = TestClient(app)
ISSUE = "2018-11-08T19:50:00Z"


def test_meteorological_wind_from_direction_is_reversed_for_downwind_spread():
    east, north = paradise_forecast._downwind_unit_vector(45)
    assert east == pytest.approx(-2 ** -0.5)
    assert north == pytest.approx(-2 ** -0.5)


def test_forecast_is_deterministic_and_uses_past_seeds_only():
    first = paradise_forecast.run_forecast(ISSUE, 49)
    second = paradise_forecast.run_forecast(ISSUE, 49)
    assert first["status"] == "predicted"
    assert first["forecast_id"] == second["forecast_id"]
    assert first["cells"] == second["cells"]
    assert first["summary"]["seed_cells"] == 182
    assert first["summary"]["predicted_new_cells"] > 0
    assert all(cell["cell_id"].startswith("P-") for cell in first["cells"])


def test_forecast_before_first_detection_does_not_invent_fire():
    result = paradise_forecast.run_forecast("2018-11-08T10:00:00Z", 60)
    assert result["status"] == "no_observations"
    assert result["cells"] == []
    assert result["seeds"] == []
    assert "does not fabricate" in result["reason"]


def test_forecast_valid_time_and_probability_bounds():
    result = paradise_forecast.run_forecast(ISSUE, 49)
    issued = datetime.fromisoformat(result["issued_at_utc"])
    valid = datetime.fromisoformat(result["valid_at_utc"])
    assert valid - issued == timedelta(minutes=49)
    probabilities = [cell["probability"] for cell in result["cells"]]
    assert probabilities
    assert all(0.0 <= value <= 1.0 for value in probabilities)
    assert all(
        cell["probability"] >= result["threshold"]
        for cell in result["cells"]
        if cell["newly_predicted"]
    )
    assert all(
        cell["arrival_minutes"] <= 49
        for cell in result["cells"]
        if cell["newly_predicted"]
    )


def test_seed_cells_are_marked_and_never_counted_as_new():
    result = paradise_forecast.run_forecast(ISSUE, 49)
    seeds = set(result["seeds"])
    assert seeds
    for cell in result["cells"]:
        if cell["cell_id"] in seeds:
            assert cell["seed"] is True
            assert cell["newly_predicted"] is False
            assert cell["arrival_minutes"] == 0


def test_lead_time_bounds_are_enforced():
    with pytest.raises(ValueError, match="lead_minutes"):
        paradise_forecast.run_forecast(ISSUE, 5)
    with pytest.raises(ValueError, match="lead_minutes"):
        paradise_forecast.run_forecast(ISSUE, 721)


def test_suppression_scenario_does_not_increase_prediction():
    baseline = paradise_forecast.run_forecast(ISSUE, 49)
    suppressed = paradise_forecast.run_forecast(
        ISSUE,
        49,
        scenario={"name": "suppression", "suppression_effectiveness": 0.9},
    )
    assert suppressed["scenario"]["name"] == "suppression"
    assert suppressed["summary"]["predicted_new_cells"] <= baseline["summary"]["predicted_new_cells"]


def test_forecast_api_and_scenario_parameters():
    baseline = client.get(f"/api/v1/paradise/forecast?at={ISSUE}&lead_minutes=49")
    assert baseline.status_code == 200
    payload = baseline.json()
    assert payload["status"] == "predicted"
    assert payload["summary"]["seed_cells"] == 182

    scenario = client.get(
        f"/api/v1/paradise/forecast?at={ISSUE}&lead_minutes=49"
        "&name=wind_shift&wind_speed_multiplier=1.6&wind_direction_delta_deg=45"
    )
    assert scenario.status_code == 200
    assert scenario.json()["scenario"]["wind_direction_delta_deg"] == 45

    invalid = client.get(f"/api/v1/paradise/forecast?at={ISSUE}&lead_minutes=9999")
    assert invalid.status_code == 422
