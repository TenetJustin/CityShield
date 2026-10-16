from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from statistics import median
from typing import Any

from .config import config_fingerprint
from .schemas import Observation, ScenarioRequest, utc_now


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
    """Transparent ensemble demonstration model, not an operational fire solver.

    The model exercises CityShield's real-time state, scenario, decision, audit
    and RSI contracts before a city and validated spread engine are selected.
    """

    model_version = "0.2.0-transparent-directional-ensemble"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.config_id = config_fingerprint(config)
        self.cells = {cell["id"]: cell for cell in config["cells"]}
        self.state = {cell_id: CellState() for cell_id in self.cells}
        self.weather = {
            "wind_speed": 4.0,
            "wind_direction": 90.0,
            "humidity": 25.0,
            "temperature": 30.0,
        }
        self.operational = {"road_closures": {}, "resource_status": {}}
        self.observations: list[Observation] = []
        self._dedupe_keys: set[str] = set()
        self.state_updated_at = utc_now()
        self.last_forecast: dict[str, Any] | None = None

    def reset(self) -> None:
        self.state = {cell_id: CellState() for cell_id in self.cells}
        self.weather = {
            "wind_speed": 4.0,
            "wind_direction": 90.0,
            "humidity": 25.0,
            "temperature": 30.0,
        }
        self.operational = {"road_closures": {}, "resource_status": {}}
        self.observations = []
        self._dedupe_keys = set()
        self.last_forecast = None
        self.state_updated_at = utc_now()

    def ingest(self, observation: Observation) -> bool:
        if observation.quality_flag != "forecast" and observation.available_at < observation.valid_at:
            raise ValueError("non-forecast available_at cannot precede valid_at")
        if observation.quality_flag == "forecast" and observation.forecast_issued_at is None:
            raise ValueError("forecast records require forecast_issued_at")
        if observation.cell_id and observation.cell_id not in self.cells:
            raise ValueError(f"unknown cell_id: {observation.cell_id}")
        key = observation.dedupe_key()
        if key in self._dedupe_keys:
            return False
        if observation.kind in {"hotspot", "perimeter"}:
            if not observation.cell_id:
                raise ValueError(f"{observation.kind} requires cell_id")
            state = self.state[observation.cell_id]
            confidence = _clamp(observation.value)
            state.burning_probability = max(state.burning_probability, confidence)
            state.fire_intensity = max(state.fire_intensity, confidence * 0.8)
        elif observation.kind in self.weather:
            self.weather[observation.kind] = float(observation.value)
        elif observation.kind == "road_closure":
            if not observation.cell_id:
                raise ValueError("road_closure requires cell_id")
            self.operational["road_closures"][observation.cell_id] = observation.value > 0
        elif observation.kind == "resource_status":
            if not observation.cell_id:
                raise ValueError("resource_status requires cell_id")
            self.operational["resource_status"][observation.cell_id] = observation.value
        self._dedupe_keys.add(key)
        self.observations.append(observation)
        self.observations.sort(key=lambda item: (item.available_at, item.valid_at, item.kind))
        self.state_updated_at = utc_now()
        self.last_forecast = None
        return True

    def _neighbors(self, cell_id: str) -> list[str]:
        cell = self.cells[cell_id]
        return [
            other_id
            for other_id, other in self.cells.items()
            if other_id != cell_id
            and abs(other["row"] - cell["row"]) + abs(other["col"] - cell["col"]) == 1
        ]

    def _wind_alignment(self, source_id: str, target_id: str, wind_direction: float) -> float:
        source = self.cells[source_id]
        target = self.cells[target_id]
        dr = target["row"] - source["row"]
        dc = target["col"] - source["col"]
        travel_direction = math.degrees(math.atan2(dc, -dr)) % 360
        downwind_direction = (wind_direction + 180.0) % 360
        difference = math.radians((travel_direction - downwind_direction + 180) % 360 - 180)
        return 0.45 + 0.55 * max(0.0, math.cos(difference))

    def _step(
        self,
        state: dict[str, CellState],
        spread_factor: float,
        weather: dict[str, float],
        suppression_effectiveness: float,
    ) -> dict[str, CellState]:
        humidity_factor = _clamp(1.0 - weather["humidity"] / 100.0)
        temperature_factor = max(0.6, min(1.4, 0.75 + weather["temperature"] / 100.0))
        wind_factor = min(2.2, 0.6 + weather["wind_speed"] / 12.0)
        next_state: dict[str, CellState] = {}
        for cell_id, current in state.items():
            cell = self.cells[cell_id]
            pressures = [
                state[neighbor].burning_probability
                * self._wind_alignment(neighbor, cell_id, weather["wind_direction"])
                for neighbor in self._neighbors(cell_id)
            ]
            neighbor_pressure = max(pressures, default=0.0)
            terrain = 0.75 + 0.5 * float(cell["slope"])
            fuel = float(cell["fuel"]) * current.remaining_fuel
            ignition = (
                neighbor_pressure
                * fuel
                * humidity_factor
                * temperature_factor
                * wind_factor
                * terrain
                * (1.0 - suppression_effectiveness)
            )
            probability = _clamp(current.burning_probability * 0.97 + ignition * spread_factor)
            intensity = _clamp(
                max(current.fire_intensity * 0.92, probability * fuel)
                * (1.0 - suppression_effectiveness * 0.5)
            )
            remaining = _clamp(current.remaining_fuel - intensity * 0.035)
            next_state[cell_id] = CellState(probability, intensity, remaining)
        return next_state

    def _scenario_weather(self, scenario: ScenarioRequest) -> dict[str, float]:
        return {
            **self.weather,
            "wind_speed": self.weather["wind_speed"] * scenario.wind_speed_multiplier,
            "wind_direction": (self.weather["wind_direction"] + scenario.wind_direction_delta_deg)
            % 360,
            "humidity": max(0.0, min(100.0, self.weather["humidity"] + scenario.humidity_delta_pct)),
        }

    def forecast(
        self,
        horizons: list[int] | None = None,
        members: int = 24,
        scenario: ScenarioRequest | None = None,
    ) -> dict[str, Any]:
        scenario = scenario or ScenarioRequest(name="baseline")
        horizons = horizons or list(self.config["forecast_horizons_minutes"])
        if members < 4 or members > 256:
            raise ValueError("members must be between 4 and 256")
        max_steps = max(horizons) // 30
        weather = self._scenario_weather(scenario)
        observation_manifest = [item.model_dump(mode="json") for item in self.observations]
        seed_source = json.dumps(
            {
                "observations": observation_manifest,
                "weather": weather,
                "scenario": scenario.model_dump(mode="json"),
                "version": self.model_version,
                "config_id": self.config_id,
            },
            sort_keys=True,
        )
        evidence_snapshot_id = hashlib.sha256(
            json.dumps(observation_manifest, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        seed = int(hashlib.sha256(seed_source.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        samples = {h: {cell_id: [] for cell_id in self.cells} for h in horizons}
        intensity_samples = {h: {cell_id: [] for cell_id in self.cells} for h in horizons}
        for _ in range(members):
            state = {cell_id: CellState(**vars(value)) for cell_id, value in self.state.items()}
            spread_factor = max(0.04, rng.gauss(0.18, 0.035))
            member_weather = {
                **weather,
                "wind_speed": max(0.0, rng.gauss(weather["wind_speed"], 0.7)),
                "humidity": max(0.0, min(100.0, rng.gauss(weather["humidity"], 2.5))),
            }
            for step in range(1, max_steps + 1):
                state = self._step(
                    state,
                    spread_factor,
                    member_weather,
                    scenario.suppression_effectiveness,
                )
                horizon = step * 30
                if horizon in samples:
                    for cell_id, value in state.items():
                        samples[horizon][cell_id].append(value.burning_probability)
                        intensity_samples[horizon][cell_id].append(value.fire_intensity)
        cells = []
        for cell_id, static in self.cells.items():
            series = []
            for horizon in horizons:
                values = samples[horizon][cell_id]
                intensities = intensity_samples[horizon][cell_id]
                series.append(
                    {
                        "horizon_minutes": horizon,
                        "p10": round(_percentile(values, 0.10), 4),
                        "p50": round(median(values), 4),
                        "p90": round(_percentile(values, 0.90), 4),
                        "intensity_p50": round(median(intensities), 4),
                    }
                )
            cells.append({"cell_id": cell_id, "static": static, "series": series})
        run_id = hashlib.sha256(
            f"{seed}|{members}|{horizons}|{evidence_snapshot_id}".encode()
        ).hexdigest()[:16]
        result = {
            "forecast_run_id": run_id,
            "evidence_snapshot_id": evidence_snapshot_id,
            "config_id": self.config_id,
            "created_at": utc_now().isoformat(),
            "model_version": self.model_version,
            "members": members,
            "probability_definition": "ensemble state proxy; not operationally calibrated",
            "weather": weather,
            "scenario": scenario.model_dump(mode="json"),
            "cells": cells,
            "quality_flags": [
                self.config.get("data_mode", "unknown"),
                "uncalibrated-model",
                "city-not-selected" if self.config["city_id"] == "TBD_US_CITY" else "city-configured",
            ],
            "provenance": {
                "observation_count": len(self.observations),
                "sources": sorted({item.source for item in self.observations}),
                "latest_available_at": max(
                    (item.available_at.isoformat() for item in self.observations), default=None
                ),
            },
        }
        if scenario.name == "baseline":
            self.last_forecast = result
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "updated_at": self.state_updated_at.isoformat(),
            "config_id": self.config_id,
            "weather": dict(self.weather),
            "operational": self.operational,
            "observation_count": len(self.observations),
            "observations": [item.model_dump(mode="json") for item in self.observations[-25:]],
            "cells": {
                cell_id: {**vars(value), "static": self.cells[cell_id]}
                for cell_id, value in self.state.items()
            },
        }
