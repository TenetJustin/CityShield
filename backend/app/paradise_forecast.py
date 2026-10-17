"""Transparent, reproducible grid spread model for the Paradise replay.

This is a deliberately small stochastic cellular automaton, not an operational
fire-behaviour model. It uses the shared 500 m cells, a declared weather
assumption, coarse terrain and a default fuel value. It never consumes data
after the forecast issue time, and every output is labelled **predicted**.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import timedelta
from functools import lru_cache
from typing import Any

from . import paradise_grid, paradise_replay


THRESHOLD = 0.5
MAX_CACHE = 48
_cache: dict[str, dict[str, Any]] = {}


def config() -> dict[str, Any]:
    return paradise_grid.replay_config()["forecast"]


@lru_cache(maxsize=1)
def model_arrays():
    artifact = paradise_grid.grid()
    cells = artifact["cells"]
    index = {cell["id"]: position for position, cell in enumerate(cells)}
    edges: list[list[tuple[int, float, float, float, float]]] = []
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for cell in cells:
        links = []
        for drow, dcol in directions:
            other_id = f"P-{cell['row'] + drow:02d}-{cell['col'] + dcol:02d}"
            other_position = index.get(other_id)
            if other_position is None:
                continue
            other = cells[other_position]
            dx = other["x_m"] - cell["x_m"]
            dy = other["y_m"] - cell["y_m"]
            distance = math.hypot(dx, dy)
            if distance == 0:
                continue
            elevation_delta = other["elevation_m"] - cell["elevation_m"]
            upslope = max(0.0, elevation_delta / distance)
            downhill = elevation_delta < 0
            slope_factor = 0.62 if downhill else 1.0 + config()["spread"]["slope_rate_gain"] * min(1.0, upslope * 2.5)
            links.append((other_position, dx / distance, dy / distance, slope_factor, float(other["fuel_value"])))
        edges.append(links)
    return cells, index, edges


def _direction_factor(alignment: float) -> float:
    lateral = config()["spread"]["lateral_factor"]
    backing = config()["spread"]["backing_factor"]
    if alignment >= 0:
        return lateral + (1.0 - lateral) * alignment * alignment
    return backing + (lateral - backing) * (1.0 + alignment)


def _weather(parameters: dict[str, Any], member: int, rng: random.Random) -> dict[str, float]:
    base = parameters["weather_assumption"]
    if member == 0:
        return {
            "wind_from_deg": float(base["wind_from_deg"]),
            "wind_speed_m_s": float(base["wind_speed_m_s"]),
            "humidity_pct": float(base["humidity_pct"]),
            "temperature_c": float(base["temperature_c"]),
        }
    return {
        "wind_from_deg": (base["wind_from_deg"] + rng.gauss(0, 8)) % 360,
        "wind_speed_m_s": max(0.0, rng.gauss(base["wind_speed_m_s"], 1.2)),
        "humidity_pct": max(1.0, min(100.0, rng.gauss(base["humidity_pct"], 2.5))),
        "temperature_c": rng.gauss(base["temperature_c"], 2.0),
    }


def _member_edge_probabilities(weather: dict[str, float], multiplier: float) -> list[list[tuple[int, float]]]:
    cells, _, edges = model_arrays()
    spread = config()["spread"]
    dt = float(config()["step_minutes"])
    wind_speed_factor = min(2.4, 0.5 + weather["wind_speed_m_s"] / 8.0)
    humidity_factor = max(0.2, 1.0 - weather["humidity_pct"] / 100.0)
    temperature_factor = max(0.7, min(1.4, 0.75 + weather["temperature_c"] / 100.0))
    bearing = math.radians(weather["wind_from_deg"])
    downwind = (math.sin(bearing), math.cos(bearing))
    result = []
    for links in edges:
        row = []
        for target, dx, dy, slope_factor, fuel in links:
            alignment = dx * downwind[0] + dy * downwind[1]
            rate = (
                spread["base_rate_per_minute"]
                * _direction_factor(alignment)
                * wind_speed_factor
                * slope_factor
                * fuel
                * humidity_factor
                * temperature_factor
                * multiplier
            )
            probability = 1.0 - math.exp(-rate * dt)
            row.append((target, probability))
        result.append(row)
    return result


def _forecast_id(at_utc: str, lead_minutes: int, seeds: list[str], scenario: dict[str, Any], threshold: float) -> str:
    payload = {
        "data_version": paradise_grid.grid()["data_version"],
        "model_version": config()["model_version"],
        "at_utc": at_utc,
        "lead_minutes": lead_minutes,
        "seeds": seeds,
        "scenario": scenario,
        "threshold": threshold,
        "parameters": config(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run_forecast(
    at: str,
    lead_minutes: int = 60,
    *,
    scenario: dict[str, Any] | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    """Forecast from observations available at ``at`` only, for one lead time."""
    if lead_minutes < config()["step_minutes"] or lead_minutes > config()["max_lead_minutes"]:
        raise ValueError(
            f"lead_minutes must be between {config()['step_minutes']} and {config()['max_lead_minutes']}"
        )
    scenario = scenario or {
        "name": "baseline",
        "wind_speed_multiplier": 1.0,
        "wind_direction_delta_deg": 0.0,
        "suppression_effectiveness": 0.0,
    }
    scenario = {
        "name": str(scenario.get("name", "custom")),
        "wind_speed_multiplier": float(scenario.get("wind_speed_multiplier", 1.0)),
        "wind_direction_delta_deg": float(scenario.get("wind_direction_delta_deg", 0.0)),
        "suppression_effectiveness": float(scenario.get("suppression_effectiveness", 0.0)),
    }
    threshold = float(threshold if threshold is not None else config()["threshold"])
    at_norm = paradise_replay.utc(at).isoformat()
    seeds = paradise_replay.seed_cells_at(at_norm)
    if not seeds:
        return {
            "status": "no_observations",
            "reason": "No FIRMS detections at or before this time. The model does not fabricate a fire.",
            "issued_at_utc": at_norm,
            "issued_at_local": paradise_replay.local_iso(at_norm),
            "lead_minutes": lead_minutes,
            "data_version": paradise_grid.grid()["data_version"],
            "model_version": config()["model_version"],
            "seeds": [],
            "cells": [],
            "summary": {"seed_cells": 0, "predicted_cells": 0},
        }
    cache_key = json.dumps(
        {"at": at_norm, "lead": lead_minutes, "seeds": seeds, "scenario": scenario, "threshold": threshold},
        sort_keys=True,
    )
    if cache_key in _cache:
        return _cache[cache_key]

    cells, index, _ = model_arrays()
    seed_positions = [index[cell_id] for cell_id in seeds if cell_id in index]
    parameters = config()
    member_count = int(parameters["members"])
    base_seed = int(_forecast_id(at_norm, lead_minutes, seeds, scenario, threshold), 16)
    step_minutes = int(parameters["step_minutes"])
    steps = max(1, math.ceil(lead_minutes / step_minutes))
    threshold = max(0.05, min(0.95, threshold))

    burn_counts = [0] * len(cells)
    arrivals: list[list[int]] = [[] for _ in cells]
    for member in range(member_count):
        rng = random.Random(base_seed + member * 1_000_003)
        weather = _weather(parameters, member, rng)
        weather["wind_speed_m_s"] = max(0.0, weather["wind_speed_m_s"] * scenario["wind_speed_multiplier"])
        weather["wind_from_deg"] = (weather["wind_from_deg"] + scenario["wind_direction_delta_deg"]) % 360
        multiplier = rng.lognormvariate(0.0, parameters["spread"]["rate_sigma"])
        multiplier *= max(0.0, 1.0 - scenario["suppression_effectiveness"])
        edge_probabilities = _member_edge_probabilities(weather, multiplier)
        burning = [False] * len(cells)
        arrival = [None] * len(cells)
        for position in seed_positions:
            burning[position] = True
            arrival[position] = 0
        active = list(seed_positions)
        for step in range(1, steps + 1):
            ignited: set[int] = set()
            for source in active:
                for target, probability in edge_probabilities[source]:
                    if not burning[target] and rng.random() < probability:
                        ignited.add(target)
            for target in ignited:
                burning[target] = True
                arrival[target] = step * step_minutes
            active.extend(ignited)
        for position, is_burning in enumerate(burning):
            if is_burning:
                burn_counts[position] += 1
                arrivals[position].append(arrival[position] or 0)

    result_cells = []
    seed_set = set(seed_positions)
    predicted_population = 0.0
    total_population = 0.0
    predicted_new = 0
    for position, cell in enumerate(cells):
        probability = burn_counts[position] / member_count
        if probability <= 0 and position not in seed_set:
            continue
        values = sorted(arrivals[position])
        arrival_minutes = values[len(values) // 2] if values else None
        is_seed = position in seed_set
        is_new = (not is_seed) and probability >= threshold and arrival_minutes is not None and arrival_minutes <= lead_minutes
        if is_new:
            predicted_new += 1
            predicted_population += float(cell["population"])
        if probability >= threshold:
            total_population += float(cell["population"])
        result_cells.append({
            "cell_id": cell["id"],
            "probability": round(probability, 4),
            "arrival_minutes": arrival_minutes,
            "seed": is_seed,
            "newly_predicted": is_new,
            "population": cell["population"],
            "status": "predicted",
        })
    result_cells.sort(key=lambda item: (-item["probability"], item["cell_id"]))
    result = {
        "status": "predicted",
        "forecast_id": _forecast_id(at_norm, lead_minutes, seeds, scenario, threshold),
        "issued_at_utc": at_norm,
        "issued_at_local": paradise_replay.local_iso(at_norm),
        "valid_at_utc": (paradise_replay.utc(at_norm) + timedelta(minutes=lead_minutes)).isoformat(),
        "lead_minutes": lead_minutes,
        "data_version": paradise_grid.grid()["data_version"],
        "grid_version": paradise_grid.grid()["grid_version"],
        "model_version": config()["model_version"],
        "threshold": threshold,
        "scenario": scenario,
        "weather_assumption": {
            **parameters["weather_assumption"],
            "ensemble_note": "Member 0 is the stated assumption; other members sample wind, humidity and temperature uncertainty.",
        },
        "seeds": seeds,
        "cells": result_cells,
        "summary": {
            "seed_cells": len(seed_positions),
            "predicted_new_cells": predicted_new,
            "cells_with_probability": len(result_cells),
            "predicted_new_population": round(predicted_population, 2),
            "predicted_total_population_at_threshold": round(total_population, 2),
            "members": member_count,
            "step_minutes": step_minutes,
            "steps": steps,
            "threshold": threshold,
        },
        "assumptions": [
            "Weather is a fixed scenario assumption, not a historical station observation.",
            "Fuel is a declared default because no LANDFIRE layer is bundled.",
            "Terrain is a coarse 7x7 interpolation, not a modeling DEM.",
            "No suppression, water availability, ember transport or structure-to-structure spread is modelled.",
            "The forecast uses only FIRMS detections acquired at or before the issue time.",
        ],
        "limitations": [
            "Uncalibrated research model; probabilities are not operational confidence.",
            "FIRMS detections are an incomplete active-fire sample, not a perimeter.",
            "Long leads crossing the overnight observation gap are extrapolations.",
        ],
    }
    if len(_cache) >= MAX_CACHE:
        _cache.pop(next(iter(_cache)))
    _cache[cache_key] = result
    return result


def comparison_series(at: str, lead_minutes: int = 60) -> dict[str, Any]:
    """Return a small baseline/current comparison for the same issue time."""
    current = run_forecast(at, lead_minutes)
    if current["status"] == "no_observations":
        return {"status": "no_observations", "reason": current["reason"]}
    seeds = current["seeds"]
    cells, index, _ = model_arrays()
    seed_positions = [index[cell_id] for cell_id in seeds]
    # No-growth persistence baseline: only the seed cells are "burning".
    current_cells = {item["cell_id"]: item for item in current["cells"]}
    baseline = []
    for position in seed_positions:
        cell = cells[position]
        baseline.append({
            "cell_id": cell["id"],
            "probability": 1.0,
            "arrival_minutes": 0,
            "seed": True,
            "newly_predicted": False,
            "population": cell["population"],
            "status": "predicted",
        })
    return {
        "issued_at_utc": current["issued_at_utc"],
        "lead_minutes": lead_minutes,
        "current": current,
        "persistence_baseline": {
            "id": "persistence",
            "description": "No growth beyond cells already detected at issue time.",
            "cells": baseline,
            "summary": {"predicted_new_cells": 0},
        },
        "current_new_cells": [item["cell_id"] for item in current["cells"] if item["newly_predicted"]],
        "current_cells": current_cells,
    }
