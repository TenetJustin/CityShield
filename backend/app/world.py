from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from statistics import median
from typing import Any

from .schemas import Observation, utc_now


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = fraction * (len(ordered) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


@dataclass
class CellState:
    burning_probability: float = 0.0
    fire_intensity: float = 0.0
    remaining_fuel: float = 1.0


class WildfireWorldModel:
    """Transparent demonstration model; not an operational fire solver."""

    model_version = "0.1.0-transparent-ensemble"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.cells = {cell["id"]: cell for cell in config["cells"]}
        self.state = {cell_id: CellState() for cell_id in self.cells}
        self.weather = {"wind_speed": 4.0, "wind_direction": 90.0, "humidity": 25.0}
        self.observations: list[Observation] = []
        self.state_updated_at = utc_now()
        self.last_forecast: dict[str, Any] | None = None

    def reset(self) -> None:
        self.state = {cell_id: CellState() for cell_id in self.cells}
        self.weather = {"wind_speed": 4.0, "wind_direction": 90.0, "humidity": 25.0}
        self.observations = []
        self.last_forecast = None
        self.state_updated_at = utc_now()

    def ingest(self, observation: Observation) -> None:
        if observation.available_at < observation.valid_at:
            raise ValueError("available_at cannot precede valid_at")
        if observation.cell_id and observation.cell_id not in self.cells:
            raise ValueError(f"unknown cell_id: {observation.cell_id}")
        if observation.kind in {"hotspot", "perimeter"}:
            if not observation.cell_id:
                raise ValueError(f"{observation.kind} requires cell_id")
            state = self.state[observation.cell_id]
            confidence = _clamp(observation.value)
            state.burning_probability = max(state.burning_probability, confidence)
            state.fire_intensity = max(state.fire_intensity, confidence * 0.8)
        elif observation.kind in self.weather:
            self.weather[observation.kind] = float(observation.value)
        self.observations.append(observation)
        self.state_updated_at = utc_now()

    def _neighbors(self, cell_id: str) -> list[str]:
        cell = self.cells[cell_id]
        return [
            other_id
            for other_id, other in self.cells.items()
            if other_id != cell_id
            and abs(other["row"] - cell["row"]) + abs(other["col"] - cell["col"]) == 1
        ]

    def _step(self, state: dict[str, CellState], spread_factor: float) -> dict[str, CellState]:
        humidity_factor = _clamp(1.0 - self.weather["humidity"] / 100.0)
        wind_factor = min(2.0, 0.6 + self.weather["wind_speed"] / 12.0)
        next_state: dict[str, CellState] = {}
        for cell_id, current in state.items():
            cell = self.cells[cell_id]
            neighbor_pressure = max(
                (state[n].burning_probability for n in self._neighbors(cell_id)), default=0.0
            )
            terrain = 0.75 + 0.5 * float(cell["slope"])
            fuel = float(cell["fuel"]) * current.remaining_fuel
            ignition = neighbor_pressure * fuel * humidity_factor * wind_factor * terrain
            probability = _clamp(current.burning_probability * 0.97 + ignition * spread_factor)
            intensity = _clamp(max(current.fire_intensity * 0.92, probability * fuel))
            remaining = _clamp(current.remaining_fuel - intensity * 0.035)
            next_state[cell_id] = CellState(probability, intensity, remaining)
        return next_state

    def forecast(self, horizons: list[int] | None = None, members: int = 24) -> dict[str, Any]:
        horizons = horizons or list(self.config["forecast_horizons_minutes"])
        max_steps = max(horizons) // 30
        seed_source = json.dumps(
            {
                "observations": [item.model_dump(mode="json") for item in self.observations],
                "weather": self.weather,
                "version": self.model_version,
            },
            sort_keys=True,
        )
        seed = int(hashlib.sha256(seed_source.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        samples = {h: {cell_id: [] for cell_id in self.cells} for h in horizons}
        for _ in range(members):
            state = {cell_id: CellState(**vars(value)) for cell_id, value in self.state.items()}
            spread_factor = max(0.04, rng.gauss(0.18, 0.035))
            for step in range(1, max_steps + 1):
                state = self._step(state, spread_factor)
                horizon = step * 30
                if horizon in samples:
                    for cell_id, value in state.items():
                        samples[horizon][cell_id].append(value.burning_probability)
        cells = []
        for cell_id, static in self.cells.items():
            series = []
            for horizon in horizons:
                values = samples[horizon][cell_id]
                series.append(
                    {
                        "horizon_minutes": horizon,
                        "p10": round(_percentile(values, 0.10), 4),
                        "p50": round(median(values), 4),
                        "p90": round(_percentile(values, 0.90), 4),
                    }
                )
            cells.append({"cell_id": cell_id, "static": static, "series": series})
        run_id = hashlib.sha256(f"{seed}|{members}|{horizons}".encode()).hexdigest()[:16]
        result = {
            "forecast_run_id": run_id,
            "created_at": utc_now().isoformat(),
            "model_version": self.model_version,
            "members": members,
            "probability_definition": "ensemble exceedance proxy; not operationally calibrated",
            "weather": dict(self.weather),
            "cells": cells,
            "quality_flags": [self.config.get("data_mode", "unknown"), "uncalibrated-model"],
        }
        self.last_forecast = result
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "updated_at": self.state_updated_at.isoformat(),
            "weather": dict(self.weather),
            "observation_count": len(self.observations),
            "cells": {
                cell_id: {**vars(value), "static": self.cells[cell_id]}
                for cell_id, value in self.state.items()
            },
        }

