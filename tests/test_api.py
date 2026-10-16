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


def test_rsi_is_shadow_only():
    client.post("/api/v1/demo/reset")
    client.post("/api/v1/demo/replay")
    response = client.post(
        "/api/v1/rsi/evaluate",
        json={"event_id": "test-event", "burned_cells": ["B1", "B2"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "shadow"

