from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_demo_end_to_end():
    assert client.post("/api/v1/demo/reset").status_code == 200
    replay = client.post("/api/v1/demo/replay")
    assert replay.status_code == 200
    payload = replay.json()
    assert payload["forecast"]["cells"]
    assert payload["decision"]["status"] == "pending_human_review"
    assert payload["forecast"]["evidence_snapshot_id"]
    assert payload["forecast"]["latency_ms"] >= 0


def test_rsi_is_shadow_only():
    client.post("/api/v1/demo/reset")
    client.post("/api/v1/demo/replay")
    response = client.post(
        "/api/v1/rsi/evaluate",
        json={"event_id": "test-event", "burned_cells": ["B1", "B2"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "shadow"


def test_readiness_exposes_only_city_specific_blockers():
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["non_city_platform_complete"] is True
    assert payload["status"] == "demo_ready"
    assert "select_city" in payload["blocking_city_specific_items"]


def test_scenario_is_paired_to_baseline():
    client.post("/api/v1/demo/reset")
    client.post("/api/v1/demo/replay")
    response = client.post(
        "/api/v1/scenarios/simulate",
        json={"name": "wind_shift", "wind_speed_multiplier": 1.5, "wind_direction_delta_deg": 90},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["simulation_run_id"]
    assert len(payload["delta"]) == 9


def test_duplicate_observation_is_idempotent():
    client.post("/api/v1/demo/reset")
    item = {
        "event_id": "dup",
        "kind": "hotspot",
        "cell_id": "A1",
        "value": 0.8,
        "unit": "confidence_0_1",
        "valid_at": "2026-01-01T00:00:00Z",
        "available_at": "2026-01-01T00:01:00Z",
        "source": "test",
        "provider_record_id": "same",
        "quality_flag": "observed",
    }
    assert client.post("/api/v1/observations", json=item).json()["accepted"] is True
    duplicate = client.post("/api/v1/observations", json=item).json()
    assert duplicate["accepted"] is False
    assert duplicate["duplicate"] is True


def test_decision_review_and_outcome_are_separate_steps():
    client.post("/api/v1/demo/reset")
    decision = client.post("/api/v1/demo/replay").json()["decision"]
    decision_id = decision["decision_run_id"]
    review = client.post(
        f"/api/v1/decisions/{decision_id}/review",
        json={"approved": True, "reviewer": "test commander", "note": "demo"},
    )
    assert review.json()["status"] == "approved_for_coordination"
    outcome = client.post(
        f"/api/v1/decisions/{decision_id}/outcome",
        json={"outcome": "not_executed", "reviewer": "test commander", "note": "exercise"},
    )
    assert outcome.json()["status"] == "closed"


def test_rsi_gate_never_changes_active_model():
    client.post("/api/v1/demo/reset")
    client.post("/api/v1/demo/replay")
    candidate = client.post(
        "/api/v1/rsi/evaluate",
        json={"event_id": "test-event", "burned_cells": ["B1", "B2"]},
    ).json()
    gated = client.post(
        f"/api/v1/rsi/candidates/{candidate['candidate_id']}/gate",
        json={
            "reviewer": "model owner",
            "held_out_replay_passed": True,
            "safety_review_passed": True,
            "note": "shadow only",
        },
    ).json()
    assert gated["status"] == "approved_for_versioned_shadow_release"
    assert gated["active_model_changed"] is False

