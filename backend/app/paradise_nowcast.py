"""Live Paradise observation-to-decision loop.

This module is intentionally small and explicit: it maps current NASA FIRMS
detections to the frozen Paradise grid, combines them with the current NOAA
hourly forecast, runs the existing versioned ensemble at 30/60/120 minutes,
and creates advisory actions that always require human review.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from datetime import datetime, timezone
from typing import Any

from . import paradise, paradise_eval, paradise_forecast, paradise_grid


HORIZONS = (30, 60, 120)
COMPASS_DEGREES = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
}


def _utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_minutes(value: str | None, now: datetime) -> int | None:
    parsed = _utc(value)
    if parsed is None:
        return None
    return max(0, round((now - parsed).total_seconds() / 60))


def _weather_input(hourly: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not hourly:
        return None
    period = hourly[0]
    direction = COMPASS_DEGREES.get(str(period.get("wind_direction", "")).upper())
    speed = period.get("wind_speed_m_s")
    humidity = period.get("humidity_pct")
    temperature = period.get("temperature")
    if None in (direction, speed, humidity, temperature):
        return None
    unit = str(period.get("temperature_unit", "F")).upper()
    temperature_c = (float(temperature) - 32.0) * 5.0 / 9.0 if unit == "F" else float(temperature)
    return {
        "wind_from_deg": direction,
        "wind_speed_m_s": float(speed),
        "humidity_pct": float(humidity),
        "temperature_c": round(temperature_c, 2),
        "status": "forecast-observation",
        "source": "NOAA NWS hourly forecast",
        "valid_at": period.get("valid_at"),
        "forecast_issued_at": period.get("forecast_issued_at"),
    }


def _mapped_observations(detections: list[dict[str, Any]]) -> tuple[list[str], int, str | None]:
    points = [
        (float(item["longitude"]), float(item["latitude"]))
        for item in detections
        if item.get("longitude") is not None and item.get("latitude") is not None
    ]
    cell_ids, outside = paradise_grid.cell_ids_for_points(points)
    acquired = sorted(item["acquired_at"] for item in detections if item.get("acquired_at"))
    return cell_ids, outside, acquired[-1] if acquired else None


def _actions(forecasts: dict[str, dict[str, Any]], seed_cells: list[str]) -> list[dict[str, Any]]:
    forecast_60 = forecasts.get("60", {})
    candidates = [item for item in forecast_60.get("cells", []) if item.get("newly_predicted")]
    candidates.sort(key=lambda item: (-(item["probability"] * max(1, item["population"])), item["cell_id"]))
    top_cells = [item["cell_id"] for item in candidates[:5]]
    exposure = forecast_60.get("summary", {}).get("predicted_new_population", 0)
    if not seed_cells:
        return [{
            "priority": 1,
            "action": "Continue source monitoring",
            "reason": "No current FIRMS detections mapped to the Paradise grid. This is an abstention, not evidence that the area is safe.",
            "target_cells": [],
            "requires_human_review": True,
        }]
    actions = [{
        "priority": 1,
        "action": "Verify satellite detections with incident staff",
        "reason": f"{len(seed_cells)} grid cells contain current FIRMS detections; satellite points can include delay and false positives.",
        "target_cells": seed_cells[:8],
        "requires_human_review": True,
    }]
    if top_cells:
        actions.append({
            "priority": 2,
            "action": "Review targeted evacuation readiness",
            "reason": f"The 60-minute model flags {len(candidates)} new cells and about {round(exposure):,} people at the reporting threshold.",
            "target_cells": top_cells,
            "requires_human_review": True,
        })
        actions.append({
            "priority": 3,
            "action": "Pre-stage response planning near highest exposure",
            "reason": "These cells rank highest by predicted probability multiplied by mapped population; routing and resource availability remain simulated.",
            "target_cells": top_cells[:3],
            "requires_human_review": True,
        })
    return actions


async def build_nowcast(force: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    live = await paradise.live_snapshot(force=force)
    now = datetime.now(timezone.utc)
    detections = live.get("satellite_detections", [])
    seed_cells, outside_grid, latest_detection = _mapped_observations(detections)
    weather = _weather_input(live.get("hourly_forecast", []))
    firms_status = live.get("sources", {}).get("nasa-firms", {}).get("status")
    nws_status = live.get("sources", {}).get("noaa-nws", {}).get("status")
    input_ready = firms_status == "ok" and nws_status == "ok" and weather is not None

    forecasts: dict[str, dict[str, Any]] = {}
    if input_ready and seed_cells:
        for horizon in HORIZONS:
            forecasts[str(horizon)] = paradise_forecast.run_forecast(
                now.isoformat(),
                horizon,
                seed_cells=seed_cells,
                weather=weather,
                source_mode="live_firms_nws",
            )

    if not input_ready:
        status = "input_incomplete"
        status_message = "Live prediction is paused because a required source or weather field is unavailable."
    elif not seed_cells:
        status = "abstained_no_observations"
        status_message = "No FIRMS detections mapped to the grid; CityShield abstained instead of inventing a fire."
    else:
        status = "advisory_ready"
        status_message = "Live inputs produced advisory forecasts and a human decision queue."

    evaluation = paradise_eval.evaluation_summary()
    confidence = {
        "label": "limited" if status == "advisory_ready" else "not_applicable",
        "reason": (
            "The model has time-forward Camp Fire replay evidence but no independent live-event calibration."
            if status == "advisory_ready"
            else "No live forecast was issued."
        ),
        "historical_evidence": evaluation,
    }
    actions = _actions(forecasts, seed_cells) if input_ready else [{
        "priority": 1,
        "action": "Restore required live inputs",
        "reason": "FIRMS and a complete NOAA hourly weather period are required before live prediction resumes.",
        "target_cells": [],
        "requires_human_review": True,
    }]
    identity_payload = {
        "fetched_at": live.get("fetched_at"),
        "latest_detection": latest_detection,
        "seed_cells": seed_cells,
        "weather": weather,
        "forecast_ids": {key: value.get("forecast_id") for key, value in forecasts.items()},
    }
    run_id = hashlib.sha256(json.dumps(identity_payload, sort_keys=True).encode()).hexdigest()[:16]
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "run_id": run_id,
        "status": status,
        "status_message": status_message,
        "area": live.get("area"),
        "issued_at_utc": now.isoformat(),
        "decision_status": "pending_human_review" if actions else "no_action",
        "observation": {
            "source": "NASA FIRMS VIIRS SNPP NRT",
            "detections": len(detections),
            "mapped_seed_cells": seed_cells,
            "outside_grid_detections": outside_grid,
            "latest_detection_at": latest_detection,
            "latest_detection_age_minutes": _age_minutes(latest_detection, now),
            "interpretation": "Active-fire points are observations, not a perimeter or proof of safety when absent.",
        },
        "weather": weather,
        "forecasts": forecasts,
        "actions": actions,
        "confidence": confidence,
        "sources": live.get("sources", {}),
        "telemetry": {
            "pipeline": ["FIRMS + NOAA", "Paradise 500 m grid", "24-member ensemble", "30/60/120 min risk", "human review queue"],
            "source_snapshot_at": live.get("fetched_at"),
            "source_snapshot_age_minutes": _age_minutes(live.get("fetched_at"), now),
            "inference_latency_ms": latency_ms,
            "runtime_architecture": platform.machine(),
            "deployment_target": "IBM LinuxONE",
            "git_commit": os.getenv("CITYSHIELD_GIT_COMMIT", "unknown"),
            "model_version": paradise_forecast.config()["model_version"],
            "grid_version": paradise_grid.grid()["grid_version"],
        },
        "safety": "Advisory research output only. Approval does not send an alert, order an evacuation or dispatch resources.",
    }
