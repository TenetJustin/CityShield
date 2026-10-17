"""Strict time-forward evaluation of Camp Fire spread against FIRMS detections.

For every pair of consecutive FIRMS snapshots the forecast is issued at the
earlier snapshot and scored against only the detections that appear after it.
No future observation is used to build the forecast. These metrics measure
agreement with *active-fire detections*, not true burned area.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from . import paradise_forecast, paradise_grid, paradise_replay


EVALUATION_PATH = paradise_grid.DATA / "camp_fire_evaluation.json"
DEFAULT_BASELINE_RATE_KMH = 1.5


def _config() -> dict[str, Any]:
    return paradise_grid.replay_config()["evaluation"]


def _bucket(lead_minutes: float) -> dict[str, Any]:
    for bucket in _config()["lead_buckets"]:
        if bucket["min_minutes"] <= lead_minutes < bucket["max_minutes"]:
            return bucket
    return _config()["lead_buckets"][-1]


def _distance_m(left: dict[str, Any], right: dict[str, Any]) -> float:
    return math.hypot(left["x_m"] - right["x_m"], left["y_m"] - right["y_m"])


def _nearest(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median_m": None, "mean_m": None, "max_m": None}
    return {
        "median_m": round(statistics.median(values), 1),
        "mean_m": round(statistics.fmean(values), 1),
        "max_m": round(max(values), 1),
    }


def score(
    predicted: set[str],
    observed: set[str],
    cells: dict[str, dict[str, Any]],
    predicted_arrivals: dict[str, float],
    observed_arrivals: dict[str, float],
) -> dict[str, Any]:
    """Score one forecast window. Pure function, unit-testable."""
    true_positive = predicted & observed
    false_positive = predicted - observed
    false_negative = observed - predicted
    union = predicted | observed
    precision = len(true_positive) / len(predicted) if predicted else None
    recall = len(true_positive) / len(observed) if observed else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else None
    )
    iou = len(true_positive) / len(union) if union else None
    predicted_distance = [
        min(_distance_m(cells[cell], cells[other]) for other in predicted)
        for cell in observed
        if predicted
    ]
    missed_distance = [
        min(_distance_m(cells[cell], cells[other]) for other in predicted)
        for cell in false_negative
        if predicted
    ]
    false_alarm_distance = [
        min(_distance_m(cells[cell], cells[other]) for other in observed)
        for cell in false_positive
        if observed
    ]
    matched = sorted(true_positive)
    arrival_errors = [
        abs(predicted_arrivals[cell] - observed_arrivals[cell])
        for cell in matched
        if cell in predicted_arrivals and cell in observed_arrivals
    ]
    observed_population = sum(float(cells[cell]["population"]) for cell in observed)
    predicted_population = sum(float(cells[cell]["population"]) for cell in predicted)
    matched_population = sum(float(cells[cell]["population"]) for cell in true_positive)
    return {
        "counts": {
            "predicted_cells": len(predicted),
            "observed_cells": len(observed),
            "true_positive": len(true_positive),
            "false_positive": len(false_positive),
            "false_negative": len(false_negative),
            "union": len(union),
            "matched_arrival_cells": len(arrival_errors),
        },
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "hit_rate": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "iou": round(iou, 4) if iou is not None else None,
        "nearest_distance": {
            "observed_to_prediction_all": _nearest(predicted_distance),
            "observed_to_prediction_missed": _nearest(missed_distance),
            "prediction_to_observation_false_positive": _nearest(false_alarm_distance),
        },
        "arrival_time": {
            "median_abs_error_minutes": round(statistics.median(arrival_errors), 1) if arrival_errors else None,
            "mean_abs_error_minutes": round(statistics.fmean(arrival_errors), 1) if arrival_errors else None,
            "matched_cells": len(arrival_errors),
        },
        "population": {
            "observed_exposed": round(observed_population, 2),
            "predicted_exposed": round(predicted_population, 2),
            "correctly_predicted_exposed": round(matched_population, 2),
            "absolute_error": round(abs(predicted_population - observed_population), 2),
            "relative_error": (
                round(abs(predicted_population - observed_population) / observed_population, 4)
                if observed_population > 0
                else None
            ),
        },
    }


def radial_predictions(
    seeds: list[str],
    lead_minutes: float,
    rate_kmh: float,
    cells: dict[str, dict[str, Any]],
) -> set[str]:
    """Isotropic constant-rate baseline; no wind, terrain or fuel variation."""
    if not seeds:
        return set()
    radius_m = rate_kmh * 1000.0 * lead_minutes / 60.0
    seed_cells = [cells[cell] for cell in seeds]
    predicted = set()
    for cell_id, cell in cells.items():
        if cell_id in seeds:
            continue
        if min(_distance_m(cell, seed) for seed in seed_cells) <= radius_m:
            predicted.add(cell_id)
    return predicted


def _observed_window(
    from_utc: str,
    to_utc: str,
    cumulative_before: set[str],
) -> tuple[set[str], dict[str, float], int]:
    start = paradise_replay.utc(from_utc)
    end = paradise_replay.utc(to_utc)
    observed: set[str] = set()
    arrivals: dict[str, float] = {}
    outside = 0
    for detection in paradise_replay.detections():
        acquired = paradise_replay.utc(detection["acquired_at"])
        if start < acquired <= end:
            cell_id = detection["cell_id"]
            if not cell_id:
                outside += 1
                continue
            if cell_id in cumulative_before:
                continue
            observed.add(cell_id)
            minutes = (acquired - start).total_seconds() / 60.0
            if cell_id not in arrivals or minutes < arrivals[cell_id]:
                arrivals[cell_id] = minutes
    return observed, arrivals, outside


def _window(
    index: int,
    from_frame: dict[str, Any],
    to_frame: dict[str, Any],
) -> dict[str, Any]:
    start = paradise_replay.utc(from_frame["at_utc"])
    end = paradise_replay.utc(to_frame["at_utc"])
    lead_minutes = round((end - start).total_seconds() / 60.0)
    bucket = _bucket(lead_minutes)
    seeds = paradise_replay.seed_cells_at(from_frame["at_utc"])
    cumulative_before = set(from_frame["cumulative_detected_cells"])
    observed, observed_arrivals, outside = _observed_window(
        from_frame["at_utc"], to_frame["at_utc"], cumulative_before
    )
    forecast = paradise_forecast.run_forecast(from_frame["at_utc"], min(lead_minutes, 720))
    if forecast.get("status") != "predicted":
        return {
            "window_id": f"firms-window-{index:02d}",
            "status": "no_forecast",
            "reason": forecast.get("reason"),
            "from_utc": from_frame["at_utc"],
            "to_utc": to_frame["at_utc"],
            "lead_minutes": lead_minutes,
            "bucket": bucket,
        }
    predicted_cells = {
        item["cell_id"]: item
        for item in forecast["cells"]
        if item.get("newly_predicted")
    }
    predicted = set(predicted_cells)
    predicted_arrivals = {
        cell_id: float(item["arrival_minutes"])
        for cell_id, item in predicted_cells.items()
        if item.get("arrival_minutes") is not None
    }
    cells = paradise_grid.cell_index()
    current = score(predicted, observed, cells, predicted_arrivals, observed_arrivals)
    persistence = score(set(), observed, cells, {}, observed_arrivals)
    radial = radial_predictions(seeds, min(lead_minutes, 720), DEFAULT_BASELINE_RATE_KMH, cells)
    radial_metrics = score(radial, observed, cells, {}, observed_arrivals)
    evidence_reasons = []
    if len(observed) < _config()["minimum_observed_cells"]:
        evidence_reasons.append(
            f"only {len(observed)} observed new cells (minimum {_config()['minimum_observed_cells']})"
        )
    if len(predicted & observed) < _config()["minimum_matched_cells"]:
        evidence_reasons.append(
            f"only {len(predicted & observed)} matched cells (minimum {_config()['minimum_matched_cells']})"
        )
    return {
        "window_id": f"firms-window-{index:02d}",
        "status": "scored",
        "from_utc": from_frame["at_utc"],
        "from_local": from_frame["at_local"],
        "to_utc": to_frame["at_utc"],
        "to_local": to_frame["at_local"],
        "lead_minutes": lead_minutes,
        "bucket": bucket,
        "forecast_id": forecast["forecast_id"],
        "seed_cells": len(seeds),
        "detections_in_window": to_frame["observation_count"],
        "detections_outside_grid": outside,
        "observed_new_cells": sorted(observed),
        "predicted_new_cells": sorted(predicted),
        "current": current,
        "baseline_persistence": persistence,
        "baseline_radial": radial_metrics,
        "evidence": {
            "status": "sufficient" if not evidence_reasons else "insufficient_evidence",
            "reasons": evidence_reasons,
        },
        "nist": {
            "used_for_spatial_scoring": False,
            "reason": "NIST spatial symbols are not digitized; only FIRMS detections are scored.",
        },
    }


def _aggregate(windows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    scored = [window for window in windows if window.get("status") == "scored"]
    totals = {"predicted_cells": 0, "observed_cells": 0, "true_positive": 0, "false_positive": 0, "false_negative": 0, "union": 0, "matched_arrival_cells": 0}
    predicted_population = 0.0
    observed_population = 0.0
    population_errors = []
    nearest_missed = []
    nearest_false_alarm = []
    arrival_errors = []
    for window in scored:
        metrics = window[variant]
        for key in totals:
            totals[key] += metrics["counts"][key]
        predicted_population += metrics["population"]["predicted_exposed"]
        observed_population += metrics["population"]["observed_exposed"]
        if metrics["population"]["observed_exposed"] > 0:
            population_errors.append(metrics["population"]["relative_error"])
        if metrics["nearest_distance"]["observed_to_prediction_missed"]["median_m"] is not None:
            nearest_missed.append(metrics["nearest_distance"]["observed_to_prediction_missed"]["median_m"])
        if metrics["nearest_distance"]["prediction_to_observation_false_positive"]["median_m"] is not None:
            nearest_false_alarm.append(metrics["nearest_distance"]["prediction_to_observation_false_positive"]["median_m"])
        if metrics["arrival_time"]["median_abs_error_minutes"] is not None:
            arrival_errors.append(metrics["arrival_time"]["median_abs_error_minutes"])
    precision = totals["true_positive"] / totals["predicted_cells"] if totals["predicted_cells"] else None
    recall = totals["true_positive"] / totals["observed_cells"] if totals["observed_cells"] else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else None
    )
    iou = totals["true_positive"] / totals["union"] if totals["union"] else None
    return {
        "windows": len(scored),
        "counts": totals,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "hit_rate": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "iou": round(iou, 4) if iou is not None else None,
        "population": {
            "observed_exposed": round(observed_population, 2),
            "predicted_exposed": round(predicted_population, 2),
            "absolute_error": round(abs(predicted_population - observed_population), 2),
            "median_relative_error": round(statistics.median(population_errors), 4) if population_errors else None,
        },
        "nearest_distance": {
            "median_miss_distance_m": round(statistics.median(nearest_missed), 1) if nearest_missed else None,
            "median_false_alarm_distance_m": round(statistics.median(nearest_false_alarm), 1) if nearest_false_alarm else None,
        },
        "arrival_time": {
            "median_abs_error_minutes": round(statistics.median(arrival_errors), 1) if arrival_errors else None,
            "matched_cells": totals["matched_arrival_cells"],
        },
    }


def _evidence(aggregate: dict[str, Any], bucket_windows: int) -> dict[str, Any]:
    reasons = []
    if bucket_windows < _config()["minimum_windows"]:
        reasons.append(f"only {bucket_windows} windows (minimum {_config()['minimum_windows']})")
    if aggregate["counts"]["observed_cells"] < _config()["minimum_observed_cells"]:
        reasons.append(
            f"only {aggregate['counts']['observed_cells']} observed new cells (minimum {_config()['minimum_observed_cells']})"
        )
    if aggregate["counts"]["true_positive"] < _config()["minimum_matched_cells"]:
        reasons.append(
            f"only {aggregate['counts']['true_positive']} matched cells (minimum {_config()['minimum_matched_cells']})"
        )
    return {
        "status": "sufficient" if not reasons else "insufficient_evidence",
        "reasons": reasons,
    }


def build_evaluation() -> dict[str, Any]:
    observation_frames = [frame for frame in paradise_replay.frames() if frame["observation_count"] > 0]
    windows = [
        _window(index, previous, current)
        for index, (previous, current) in enumerate(zip(observation_frames, observation_frames[1:]), start=1)
    ]
    by_bucket = {}
    for bucket in _config()["lead_buckets"]:
        selected = [window for window in windows if window.get("bucket", {}).get("id") == bucket["id"]]
        current = _aggregate(selected, "current")
        persistence = _aggregate(selected, "baseline_persistence")
        radial = _aggregate(selected, "baseline_radial")
        by_bucket[bucket["id"]] = {
            "id": bucket["id"],
            "label": bucket["label"],
            "min_minutes": bucket["min_minutes"],
            "max_minutes": bucket["max_minutes"],
            "window_count": len(selected),
            "current": current,
            "baseline_persistence": persistence,
            "baseline_radial": radial,
            "delta_vs_persistence": {
                "recall": round((current["recall"] or 0) - (persistence["recall"] or 0), 4),
                "iou": round((current["iou"] or 0) - (persistence["iou"] or 0), 4),
            },
            "delta_vs_radial": {
                "recall": round((current["recall"] or 0) - (radial["recall"] or 0), 4),
                "iou": round((current["iou"] or 0) - (radial["iou"] or 0), 4),
            },
            "evidence": _evidence(current, len(selected)),
        }
    overall_current = _aggregate(windows, "current")
    overall_persistence = _aggregate(windows, "baseline_persistence")
    overall_radial = _aggregate(windows, "baseline_radial")
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_id": "camp-fire-2018",
        "data_version": paradise_grid.grid()["data_version"],
        "grid_version": paradise_grid.grid()["grid_version"],
        "model_version": paradise_forecast.config()["model_version"],
        "replay_id": paradise_replay.replay_id(),
        "protocol": {
            "issue_rule": "forecast at FIRMS snapshot t0 using only detections with acquired_at <= t0",
            "validation_rule": "score against cells first detected in (t0, t1] at the next FIRMS snapshot",
            "positive_definition": "a 500 m cell containing at least one FIRMS detection",
            "probability_threshold": _config()["probability_threshold"],
            "baselines": {
                "persistence": "no growth beyond cells already detected at t0",
                "radial": f"isotropic constant {DEFAULT_BASELINE_RATE_KMH} km/h growth from the t0 cells",
            },
            "nist": "NIST windows are verified time constraints only; NIST spatial symbols are not digitized and are not scored.",
        },
        "parameters": {
            "evaluation": _config(),
            "forecast": paradise_forecast.config(),
            "baseline_radial_rate_kmh": DEFAULT_BASELINE_RATE_KMH,
        },
        "windows": windows,
        "by_lead": by_bucket,
        "overall": {
            "current": overall_current,
            "baseline_persistence": overall_persistence,
            "baseline_radial": overall_radial,
        },
        "limitations": [
            "FIRMS detections are an incomplete active-fire sample, not a burn scar or perimeter.",
            "The first five hours of the fire have no FIRMS detections and are not scored.",
            "The 688-minute overnight gap dominates the long-lead bucket; long-lead results are extrapolations.",
            "Weather is a fixed scenario assumption and fuel is a default; the model is uncalibrated.",
            "NIST observations cannot be scored until their symbols are digitized and reviewed.",
            "Precision and recall answer detection agreement, not life-safety performance.",
        ],
    }


@lru_cache(maxsize=1)
def cached_evaluation() -> dict[str, Any]:
    if EVALUATION_PATH.exists():
        package = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
        if (
            package.get("data_version") == paradise_grid.grid()["data_version"]
            and package.get("model_version") == paradise_forecast.config()["model_version"]
            and package.get("replay_id") == paradise_replay.replay_id()
        ):
            return package
    return build_evaluation()


def evaluation_summary() -> dict[str, Any]:
    package = cached_evaluation()
    return {
        "data_version": package["data_version"],
        "model_version": package["model_version"],
        "replay_id": package["replay_id"],
        "generated_at": package["generated_at"],
        "protocol": package["protocol"],
        "by_lead": package["by_lead"],
        "overall": package["overall"],
        "limitations": package["limitations"],
    }
