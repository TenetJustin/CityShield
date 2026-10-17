from fastapi.testclient import TestClient

from backend.app import paradise_grid, paradise_response
from backend.app.main import app


client = TestClient(app)
EARLY = "2018-11-08T14:25:00Z"
LATE = "2018-11-08T19:50:00Z"


def test_evacuation_is_deterministic_and_labelled_simulated():
    first = paradise_response.simulate_evacuation(EARLY)
    second = paradise_response.simulate_evacuation(EARLY)
    assert first["status"] == "simulated"
    assert first["scenario"] == "evacuation"
    assert first["simulation_id"] == second["simulation_id"]
    assert first["summary"] == second["summary"]
    assert first["data_version"] == paradise_grid.grid()["data_version"]
    assert first["summary"]["total_population"] > 20_000
    assert first["summary"]["evacuated_people"] > 0
    assert all(shelter["status"] == "scenario-assumption" for shelter in first["shelters"])
    assert first["timeline"]
    assert any("not resident locations" in item for item in first["assumptions"])
    accounted = (
        first["summary"]["pre_evacuated_people"]
        + first["summary"]["evacuated_people"]
        + first["summary"]["unaccommodated_people"]
        + first["summary"]["trapped_people"]
        + first["summary"]["un_evacuated_people"]
    )
    assert abs(accounted - first["summary"]["total_population"]) <= 0.3
    assert first["summary"]["still_moving_people"] == 0
    assert first["summary"]["clearance_status"] in {"complete", "incomplete"}
    if first["summary"]["clearance_status"] == "incomplete":
        assert first["summary"]["clearance_minutes"] is None


def test_hazard_setting_changes_simulation_identity():
    with_hazard = paradise_response.simulate_evacuation(LATE, include_fire_hazard=True)
    without_hazard = paradise_response.simulate_evacuation(LATE, include_fire_hazard=False)
    assert with_hazard["simulation_id"] != without_hazard["simulation_id"]
    assert with_hazard["model_version"] == without_hazard["model_version"]
    assert with_hazard["fire_hazard"]["forecast_id"]


def test_evacuation_pre_share_reduces_late_demand():
    early = paradise_response.simulate_evacuation(EARLY, include_fire_hazard=False)
    late = paradise_response.simulate_evacuation(LATE, include_fire_hazard=False)
    assert early["summary"]["pre_evacuated_people"] == 0
    assert late["summary"]["pre_evacuated_people"] > 0
    assert late["summary"]["population_at_risk"] < early["summary"]["population_at_risk"]
    assert late["fire_hazard"]["status"] == "disabled_for_comparison"


def test_late_order_with_predicted_fire_traps_more_people():
    without_hazard = paradise_response.simulate_evacuation(LATE, include_fire_hazard=False)
    with_hazard = paradise_response.simulate_evacuation(LATE, include_fire_hazard=True)
    assert with_hazard["fire_hazard"]["status"] == "predicted"
    assert with_hazard["summary"]["trapped_people"] > without_hazard["summary"]["trapped_people"]
    assert with_hazard["summary"]["trapped_people"] > 0
    assert with_hazard["summary"]["trapped_people"] != without_hazard["summary"]["trapped_people"]


def test_shelter_capacity_shortfall_is_visible():
    result = paradise_response.simulate_evacuation(LATE, shelter_capacity_factor=0.5, include_fire_hazard=False)
    assert result["summary"]["unaccommodated_people"] > 0
    demand = sum(row["population"] for row in result["cell_flows"])
    capacity = sum(shelter["capacity"] for shelter in result["shelters"])
    assert demand > capacity
    for shelter in result["shelters"]:
        assert shelter["peak_occupancy"] <= shelter["capacity"] + 0.01
        assert shelter["assigned_people"] <= shelter["capacity"] + 0.01
    for row in result["cell_flows"]:
        assert abs(row["assigned_people"] + row["unassigned_people"] - row["population"]) <= 0.2
    assert abs(
        sum(row["unassigned_people"] for row in result["cell_flows"])
        - result["summary"]["unassigned_population"]
    ) <= 0.3


def test_compare_evacuation_uses_same_seed_and_reports_each_order_time():
    result = paradise_response.compare_evacuation(include_fire_hazard=True)
    assert result["status"] == "simulated"
    assert len(result["scenarios"]) == 3
    ids = [item["id"] for item in result["scenarios"]]
    assert ids == ["early", "mid", "late"]
    assert result["comparison"][0]["evacuated_people"] >= result["comparison"][-1]["evacuated_people"]
    assert any(item["fire_hazard"]["status"] == "no_forecast" for item in result["scenarios"])
    assert result["scenarios"][-1]["fire_hazard"]["status"] == "predicted"


def test_resource_strategies_trade_response_time_for_exposure():
    weighted = paradise_response.simulate_resources(LATE, lead_minutes=120, strategy="exposure_weighted")
    nearest = paradise_response.simulate_resources(LATE, lead_minutes=120, strategy="nearest_first")
    none = paradise_response.simulate_resources(LATE, lead_minutes=120, strategy="none")
    assert weighted["status"] == "simulated"
    assert weighted["summary"]["resources_used"] == 6
    assert weighted["summary"]["protected_population"] > nearest["summary"]["protected_population"]
    assert weighted["summary"]["mean_response_minutes"] >= nearest["summary"]["mean_response_minutes"]
    assert none["summary"]["resources_used"] == 0
    assert none["summary"]["protected_population"] == 0
    assert weighted["water_status"] == "not_available"
    assert any("simulated" in item.lower() for item in weighted["assumptions"])
    assert weighted["simulation_id"] != nearest["simulation_id"]
    assert weighted["model_version"] == paradise_response.MODEL_VERSION


def test_resource_simulation_before_observations_does_not_dispatch():
    result = paradise_response.simulate_resources(EARLY, lead_minutes=120)
    assert result["status"] == "no_forecast"
    assert result["assignments"] == []


def test_evacuation_api_endpoints():
    response = client.post(
        "/api/v1/paradise/evacuation/simulate",
        json={"order_at_utc": LATE, "seed": 20181108, "include_fire_hazard": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "simulated"
    assert payload["order_at_utc"].startswith("2018-11-08T19:50")
    assert payload["summary"]["trapped_people"] > 0

    compare = client.post(
        "/api/v1/paradise/evacuation/compare",
        json={"include_fire_hazard": True},
    )
    assert compare.status_code == 200
    assert len(compare.json()["scenarios"]) == 3

    invalid = client.post(
        "/api/v1/paradise/evacuation/simulate",
        json={"order_at_utc": "not-a-time"},
    )
    assert invalid.status_code == 422


def test_resource_and_response_config_api_endpoints():
    response = client.post(
        "/api/v1/paradise/resources/simulate",
        json={"at_utc": LATE, "lead_minutes": 120, "strategy": "exposure_weighted"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "simulated"
    assert len(payload["assignments"]) == 6

    config = client.get("/api/v1/paradise/response/config")
    assert config.status_code == 200
    payload = config.json()
    assert payload["evacuation"]["shelters"][0]["status"] == "scenario-assumption"
    assert payload["resources"]["water_status"] == "not_available"
    assert "synthetic" in payload["status_policy"]["residents"]
