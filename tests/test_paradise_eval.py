from fastapi.testclient import TestClient

from backend.app import paradise_eval, paradise_grid
from backend.app.main import app


client = TestClient(app)


def cell(cell_id, x, y, population=10.0):
    return {"cell_id": cell_id, "x_m": x, "y_m": y, "population": population}


def test_score_is_a_pure_confusion_matrix_with_distance_and_population():
    cells = {
        "A": cell("A", 0, 0, 10),
        "B": cell("B", 500, 0, 20),
        "C": cell("C", 1000, 0, 30),
    }
    result = paradise_eval.score(
        predicted={"A", "B"},
        observed={"B", "C"},
        cells=cells,
        predicted_arrivals={"A": 10, "B": 20},
        observed_arrivals={"B": 25, "C": 30},
    )
    assert result["counts"] == {
        "predicted_cells": 2,
        "observed_cells": 2,
        "true_positive": 1,
        "false_positive": 1,
        "false_negative": 1,
        "union": 3,
        "matched_arrival_cells": 1,
    }
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["iou"] == round(1 / 3, 4)
    assert result["arrival_time"]["median_abs_error_minutes"] == 5
    assert result["nearest_distance"]["observed_to_prediction_missed"]["median_m"] == 500
    assert result["population"]["observed_exposed"] == 50
    assert result["population"]["predicted_exposed"] == 30


def test_score_with_empty_prediction_is_explicit_not_infinite():
    cells = {"A": cell("A", 0, 0), "B": cell("B", 500, 0)}
    result = paradise_eval.score(set(), {"A"}, cells, {}, {"A": 10})
    assert result["precision"] is None
    assert result["recall"] == 0.0
    assert result["iou"] == 0.0
    assert result["nearest_distance"]["observed_to_prediction_missed"]["median_m"] is None


def test_radial_baseline_is_isotropic_and_rate_limited():
    cells = {
        "A": cell("A", 0, 0),
        "B": cell("B", 500, 0),
        "C": cell("C", 2000, 0),
    }
    assert paradise_eval.radial_predictions(["A"], 60, 1.5, cells) == {"B"}
    assert "C" in paradise_eval.radial_predictions(["A"], 120, 1.5, cells)


def test_evaluation_package_is_time_forward_and_versioned():
    package = paradise_eval.cached_evaluation()
    assert package["data_version"] == paradise_grid.grid()["data_version"]
    assert package["replay_id"]
    assert len(package["windows"]) == 8
    for window in package["windows"]:
        assert window["from_utc"] < window["to_utc"]
        assert window["lead_minutes"] > 0
        assert window["nist"]["used_for_spatial_scoring"] is False
    short = package["by_lead"]["short"]
    assert short["evidence"]["status"] == "sufficient"
    assert short["current"]["recall"] > short["baseline_persistence"]["recall"]
    assert short["current"]["counts"]["matched_arrival_cells"] > 0
    long = package["by_lead"]["long"]
    assert long["evidence"]["status"] == "insufficient_evidence"
    assert long["evidence"]["reasons"]


def test_evaluation_short_lead_metrics_are_not_suspiciously_perfect():
    short = paradise_eval.cached_evaluation()["by_lead"]["short"]["current"]
    assert 0 < short["precision"] < 0.9
    assert 0 < short["recall"] < 0.95
    assert 0 < short["iou"] < 0.9
    assert short["population"]["observed_exposed"] > 0


def test_evaluation_api_endpoints():
    response = client.get("/api/v1/paradise/evaluation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["protocol"]["issue_rule"].startswith("forecast at FIRMS snapshot")
    assert set(payload["by_lead"]) == {"short", "medium", "long"}

    summary = client.get("/api/v1/paradise/evaluation/summary")
    assert summary.status_code == 200
    assert summary.json()["model_version"] == paradise_eval.cached_evaluation()["model_version"]
