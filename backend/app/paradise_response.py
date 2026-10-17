"""Simulated resident evacuation and firefighting-resource allocation.

Everything in this module is a **scenario simulation**. It consumes aggregated
ACS cell population, never resident locations, and it dispatches simulated
vehicles, crews and aircraft, never real units. The road graph, shelters,
capacities, departure behaviour and effectiveness values are declared
assumptions, not verified operational data.

The model is intentionally aggregate and queue-based:

* one 500 m cell is one graph node when it contains Census road length;
* vehicles traverse one edge per simulated minute and share edge capacity;
* walkers use a straight-line 5 km/h assumption;
* shelters are two scenario staging areas, not official shelters;
* predicted fire arrival can block an edge or trap a platoon;
* every output carries ``status: "simulated"`` and the assumption list.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import random
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from . import paradise_forecast, paradise_grid, paradise_replay


DEFAULT_SEED = 20181108
MODEL_VERSION = "paradise-response-0.1.1"


def _simulation_id(*parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def config() -> dict[str, Any]:
    return paradise_grid.replay_config()


@lru_cache(maxsize=1)
def road_graph() -> dict[str, Any]:
    """Four-neighbour road graph with speed and capacity assumptions."""
    artifact = paradise_grid.grid()
    cells = artifact["cells"]
    index = {cell["id"]: position for position, cell in enumerate(cells)}
    nodes = [position for position, cell in enumerate(cells) if cell["road_length_m"] > 0]
    node_set = set(nodes)
    adjacency: dict[int, list[tuple[int, float, float]]] = {position: [] for position in nodes}
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for position in nodes:
        cell = cells[position]
        for drow, dcol in directions:
            other_id = f"P-{cell['row'] + drow:02d}-{cell['col'] + dcol:02d}"
            other = index.get(other_id)
            if other is None or other not in node_set:
                continue
            major = cell["major_road_length_m"] > 0 or cells[other]["major_road_length_m"] > 0
            speed_kmh = 40.0 if major else 25.0
            travel_minutes = 0.5 / speed_kmh * 60.0
            base_capacity = config()["evacuation"]["road_capacity_vph"]["major" if major else "local"]
            scale = max(0.15, min(1.2, (cell["road_length_m"] + cells[other]["road_length_m"]) / 800.0))
            capacity_vph = base_capacity * scale
            adjacency[position].append((other, travel_minutes, capacity_vph))
    return {
        "cells": cells,
        "index": index,
        "nodes": nodes,
        "node_set": node_set,
        "adjacency": adjacency,
    }


def dijkstra(start: int) -> tuple[dict[int, float], dict[int, int]]:
    graph = road_graph()
    adjacency = graph["adjacency"]
    distances: dict[int, float] = {start: 0.0}
    previous: dict[int, int] = {}
    heap = [(0.0, start)]
    while heap:
        distance, node = heapq.heappop(heap)
        if distance > distances.get(node, math.inf):
            continue
        for target, travel, _capacity in adjacency.get(node, []):
            candidate = distance + travel
            if candidate < distances.get(target, math.inf):
                distances[target] = candidate
                previous[target] = node
                heapq.heappush(heap, (candidate, target))
    return distances, previous


def _nearest_node(longitude: float, latitude: float) -> int:
    graph = road_graph()
    grid = graph["cells"]
    target_x = (longitude - paradise_grid.grid()["crs"]["origin"]["longitude"]) * paradise_grid.grid()["crs"]["meters_per_degree_longitude"]
    target_y = (latitude - paradise_grid.grid()["crs"]["origin"]["latitude"]) * paradise_grid.grid()["crs"]["meters_per_degree_latitude"]
    best = None
    best_distance = math.inf
    for position in graph["nodes"]:
        cell = grid[position]
        distance = math.hypot(cell["x_m"] - target_x, cell["y_m"] - target_y)
        if distance < best_distance:
            best_distance = distance
            best = position
    return best


def _path(previous: dict[int, int], start: int, shelter: int) -> list[int]:
    if start == shelter:
        return [shelter]
    path = [start]
    node = start
    seen = set()
    while node != shelter and node in previous and node not in seen:
        seen.add(node)
        node = previous[node]
        path.append(node)
    if len(path) < 2 or path[-1] != shelter:
        return []
    return path


@lru_cache(maxsize=1)
def shelter_plan() -> list[dict[str, Any]]:
    graph = road_graph()
    shelters = []
    for item in config()["evacuation"]["shelters"]:
        cell = paradise_grid.cell_index().get(item["cell_id"])
        if cell is None:
            raise ValueError(f"shelter cell not found: {item['cell_id']}")
        node = graph["index"].get(item["cell_id"])
        if node is None or node not in graph["node_set"]:
            node = _nearest_node(cell["centroid"]["longitude"], cell["centroid"]["latitude"])
        distances, previous = dijkstra(node)
        shelters.append({
            **item,
            "node": node,
            "distances": distances,
            "previous": previous,
        })
    return shelters


def _demand_table(pre_evacuated_share: float = 0.0) -> list[dict[str, Any]]:
    grid = paradise_grid.grid()
    evacuation = config()["evacuation"]
    graph = road_graph()
    shelters = shelter_plan()
    rows = []
    for position, cell in enumerate(grid["cells"]):
        if cell["population"] <= 0:
            continue
        road_position = graph["index"].get(cell["id"])
        distances = []
        for shelter in shelters:
            distance = shelter["distances"].get(road_position, math.inf) if road_position is not None else math.inf
            distances.append(distance)
        nearest = min(range(len(shelters)), key=lambda index: distances[index])
        effective_population = float(cell["population"]) * (1.0 - pre_evacuated_share)
        rows.append({
            "position": position,
            "cell_id": cell["id"],
            "population": float(cell["population"]),
            "remaining_population": effective_population,
            "vehicle_people": effective_population * evacuation["vehicle_ownership"],
            "walking_people": effective_population * evacuation["walking_share"],
            "nearest_shelter": shelters[nearest]["id"],
            "distance_minutes": distances[nearest],
            "distances": distances,
        })
    return rows


def _assign_shelters(rows: list[dict[str, Any]], capacity_factor: float) -> None:
    shelters = shelter_plan()
    remaining = {
        shelter["id"]: shelter["capacity_people"] * capacity_factor
        for shelter in shelters
    }
    for row in sorted(rows, key=lambda item: item["distance_minutes"]):
        order = sorted(range(len(shelters)), key=lambda index: row["distances"][index])
        assigned = False
        for index in order:
            shelter = shelters[index]
            if remaining[shelter["id"]] <= 0:
                continue
            path = _path(shelter["previous"], row["position"], shelter["node"])
            if not path:
                continue
            assigned_people = min(
                row["remaining_population"], remaining[shelter["id"]]
            )
            row["shelter_id"] = shelter["id"]
            row["shelter_node"] = shelter["node"]
            row["shelter_index"] = index
            row["assigned_people"] = assigned_people
            row["unassigned_people"] = row["remaining_population"] - assigned_people
            row["path"] = path
            remaining[shelter["id"]] -= assigned_people
            assigned = True
            break
        if not assigned:
            row["shelter_id"] = None
            row["shelter_node"] = None
            row["shelter_index"] = None
            row["assigned_people"] = 0.0
            row["unassigned_people"] = row["remaining_population"]
            row["path"] = []
            row["walking_minutes"] = None


def _walking_minutes(row: dict[str, Any]) -> float:
    if row.get("shelter_index") is None:
        return math.inf
    shelter = shelter_plan()[row["shelter_index"]]
    cell = paradise_grid.grid()["cells"][row["position"]]
    shelter_cell = paradise_grid.cell_index()[shelter["cell_id"]]
    distance_m = math.hypot(cell["x_m"] - shelter_cell["x_m"], cell["y_m"] - shelter_cell["y_m"])
    speed_kmh = config()["evacuation"]["walking_speed_kmh"]
    return distance_m / (speed_kmh * 1000.0 / 60.0)


def _hazard_map(order_at_utc: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    lead = config()["evacuation"]["max_simulation_minutes"]
    forecast = paradise_forecast.run_forecast(order_at_utc, min(lead, 720))
    if forecast.get("status") != "predicted":
        return {}, {
            "status": "no_forecast",
            "reason": forecast.get("reason", "No forecast at the order time."),
        }
    hazard = {}
    for item in forecast["cells"]:
        if item.get("arrival_minutes") is None:
            continue
        hazard[item["cell_id"]] = {
            "arrival_minutes": float(item["arrival_minutes"]),
            "probability": float(item["probability"]),
        }
    return hazard, {
        "status": "predicted",
        "forecast_id": forecast["forecast_id"],
        "lead_minutes": forecast["lead_minutes"],
        "issued_at_utc": forecast["issued_at_utc"],
        "threshold": forecast["threshold"],
        "note": "Fire arrival is a model prediction from the order time, not an observed perimeter.",
    }


def simulate_evacuation(
    order_at_utc: str,
    *,
    seed: int = DEFAULT_SEED,
    shelter_capacity_factor: float = 1.0,
    max_minutes: int | None = None,
    include_fire_hazard: bool = True,
) -> dict[str, Any]:
    order_at = paradise_replay.utc(order_at_utc)
    evacuation = config()["evacuation"]
    max_minutes = max_minutes or int(evacuation["max_simulation_minutes"])
    if shelter_capacity_factor <= 0 or shelter_capacity_factor > 3:
        raise ValueError("shelter_capacity_factor must be between 0 and 3")
    pre_config = evacuation.get("pre_evacuation", {})
    reference = pre_config.get("reference_at_utc")
    if reference:
        reference_at = paradise_replay.utc(reference)
        hours = max(0.0, (order_at - reference_at).total_seconds() / 3600.0)
        pre_evacuated_share = min(float(pre_config.get("max_share", 0.0)), hours * float(pre_config.get("share_per_hour", 0.0)))
    else:
        pre_evacuated_share = 0.0
    rows = _demand_table(pre_evacuated_share)
    _assign_shelters(rows, shelter_capacity_factor)
    if include_fire_hazard:
        hazards, hazard_status = _hazard_map(order_at.isoformat())
    else:
        hazards, hazard_status = {}, {
            "status": "disabled_for_comparison",
            "reason": "Fire hazard is disabled for a pure order-time/capacity comparison; this is not evidence of safety.",
        }
    threshold = paradise_forecast.config()["threshold"]
    households = float(evacuation["household_size"])
    shelters = shelter_plan()
    shelter_state = {
        shelter["id"]: {
            "id": shelter["id"],
            "label": shelter["label"],
            "cell_id": shelter["cell_id"],
            "capacity": round(shelter["capacity_people"] * shelter_capacity_factor, 2),
            "assigned_people": 0.0,
            "evacuated_people": 0.0,
            "unaccommodated_people": 0.0,
            "occupancy": 0.0,
            "peak_occupancy": 0.0,
            "off_grid_minutes": shelter.get("off_grid_minutes", 0),
            "reception_distance_km": shelter.get("reception_distance_km"),
            "outside_grid": shelter.get("outside_grid", False),
            "status": "scenario-assumption",
        }
        for shelter in shelters
    }
    for row in rows:
        if row["shelter_id"]:
            shelter_state[row["shelter_id"]]["assigned_people"] += row["assigned_people"]

    platoons = []
    total_population = 0.0
    unassigned_people = 0.0
    for row in rows:
        total_population += row["population"]
        unassigned_people += row.get("unassigned_people", 0.0)
        if not row["shelter_id"] or not row["path"]:
            continue
        delay_rng = random.Random(seed + row["position"] * 7919)
        delay = max(0.0, min(180.0, delay_rng.lognormvariate(math.log(evacuation["order_delay_minutes"]["median"]), evacuation["order_delay_minutes"]["sigma"])))
        row["departure_minute"] = round(delay, 1)
        assigned_share = (
            row["assigned_people"] / row["remaining_population"]
            if row["remaining_population"] > 0
            else 0.0
        )
        assigned_vehicle_people = row["vehicle_people"] * assigned_share
        assigned_walking_people = row["walking_people"] * assigned_share
        row["assigned_vehicle_people"] = assigned_vehicle_people
        row["assigned_walking_people"] = assigned_walking_people
        vehicles = assigned_vehicle_people / households
        if vehicles > 0:
            platoons.append({
                "count": vehicles,
                "home": row["cell_id"],
                "shelter_id": row["shelter_id"],
                "path": row["path"],
                "position": 0,
                "departure": delay,
                "walking": False,
                "people_per_vehicle": households,
            })
        walkers = assigned_walking_people
        if walkers > 0:
            walking = _walking_minutes(row)
            platoons.append({
                "count": walkers,
                "home": row["cell_id"],
                "shelter_id": row["shelter_id"],
                "path": [],
                "position": 0,
                "departure": delay + walking,
                "walking": True,
                "people_per_vehicle": 1.0,
            })

    remaining_population = total_population * (1.0 - pre_evacuated_share)
    cells = paradise_grid.grid()["cells"]
    evacuated = 0.0
    unaccommodated = 0.0
    trapped = 0.0
    last_delivery = 0.0
    vehicle_minutes = 0.0
    free_flow_vehicle_minutes = 0.0
    for platoon in platoons:
        if platoon["walking"]:
            continue
        free_flow_vehicle_minutes += platoon["count"] * max(1.0, len(platoon["path"]) - 1) * 1.0
    off_grid_minutes = {shelter["id"]: float(shelter.get("off_grid_minutes", 0)) for shelter in shelters}
    timeline = []
    released = set()
    external_pending = []

    def burning(cell_id: str, minute: float) -> bool:
        hazard = hazards.get(cell_id)
        return bool(hazard and hazard["probability"] >= threshold and hazard["arrival_minutes"] <= minute)

    for minute in range(max_minutes + 1):
        used_edges: dict[tuple[int, int], float] = {}
        deliver = []
        new_platoons = []
        for index, platoon in enumerate(platoons):
            if index in released or platoon["count"] <= 0:
                continue
            if minute < platoon["departure"]:
                continue
            if platoon["walking"]:
                if burning(platoon["home"], minute):
                    trapped += platoon["count"]
                    platoon["count"] = 0.0
                    released.add(index)
                    continue
                external_pending.append({
                    "count": platoon["count"],
                    "shelter_id": platoon["shelter_id"],
                    "people_per_vehicle": 1.0,
                    "home": platoon["home"],
                    "due": minute + float(off_grid_minutes.get(platoon["shelter_id"], 0)),
                })
                platoon["count"] = 0.0
                released.add(index)
                continue
            path = platoon["path"]
            position = platoon["position"]
            current = path[position]
            current_cell = cells[current]
            if burning(current_cell["id"], minute):
                trapped += platoon["count"] * platoon["people_per_vehicle"]
                platoon["count"] = 0.0
                released.add(index)
                continue
            if position >= len(path) - 1:
                deliver.append(platoon)
                released.add(index)
                continue
            next_node = path[position + 1]
            next_cell = cells[next_node]
            if burning(next_cell["id"], minute):
                continue
            edge = (current, next_node)
            capacity = 0.0
            for target, _travel, capacity_vph in road_graph()["adjacency"].get(current, []):
                if target == next_node:
                    capacity = capacity_vph / 60.0
                    break
            remaining_capacity = max(0.0, capacity - used_edges.get(edge, 0.0))
            moved = min(platoon["count"], remaining_capacity)
            if moved <= 0:
                continue
            used_edges[edge] = used_edges.get(edge, 0.0) + moved
            platoon["count"] -= moved
            new_position = position + 1
            if new_position >= len(path) - 1:
                external_pending.append({
                    "count": moved,
                    "shelter_id": platoon["shelter_id"],
                    "people_per_vehicle": platoon["people_per_vehicle"],
                    "home": platoon["home"],
                    "due": minute + float(off_grid_minutes.get(platoon["shelter_id"], 0)),
                })
            else:
                new_platoons.append({**platoon, "count": moved, "position": new_position})
        platoons.extend(new_platoons)
        due_now = [item for item in external_pending if item["due"] <= minute]
        external_pending = [item for item in external_pending if item["due"] > minute]
        deliver.extend(due_now)
        for platoon in deliver:
            state = shelter_state.get(platoon["shelter_id"])
            people = platoon["count"] * platoon["people_per_vehicle"]
            platoon["count"] = 0.0
            if state is None:
                unaccommodated += people
                continue
            capacity_left = max(0.0, state["capacity"] - state["occupancy"])
            take = min(people, capacity_left)
            state["occupancy"] += take
            state["evacuated_people"] += take
            state["peak_occupancy"] = max(state["peak_occupancy"], state["occupancy"])
            evacuated += take
            if people > take:
                state["unaccommodated_people"] += people - take
                unaccommodated += people - take
            if take > 0:
                last_delivery = max(last_delivery, float(minute))
        for platoon in platoons:
            if platoon.get("walking"):
                continue
            if platoon["count"] > 0 and minute >= platoon["departure"]:
                vehicle_minutes += platoon["count"]
        if minute % 5 == 0:
            queued = sum(
                platoon["count"] for index, platoon in enumerate(platoons)
                if not platoon["walking"] and index not in released and platoon["count"] > 0 and minute >= platoon["departure"]
            )
            timeline.append({
                "minute": minute,
                "evacuated_people": round(evacuated, 1),
                "queued_vehicles": round(queued, 1),
                "trapped_people": round(trapped, 1),
                "unaccommodated_people": round(unaccommodated + unassigned_people, 1),
                "shelter_occupancy": {key: round(value["occupancy"], 1) for key, value in shelter_state.items()},
            })
        accounted_people = evacuated + unaccommodated + trapped + unassigned_people
        if minute > 0 and accounted_people >= remaining_population - 0.01:
            break

    still_moving = sum(
        platoon["count"] * platoon["people_per_vehicle"]
        for platoon in platoons
        if platoon["count"] > 0 and not platoon.get("walking")
    ) + sum(
        item["count"] * item["people_per_vehicle"] for item in external_pending
    )
    still_walking = sum(
        platoon["count"] for platoon in platoons
        if platoon["count"] > 0 and platoon.get("walking")
    )
    unaccommodated_total = unaccommodated + unassigned_people
    un_evacuated = max(0.0, remaining_population - evacuated - unaccommodated_total - trapped)
    clearance_complete = (
        trapped <= 0.01
        and unaccommodated_total <= 0.01
        and un_evacuated <= 0.01
        and still_moving + still_walking <= 0.01
    )
    congestion = vehicle_minutes / free_flow_vehicle_minutes if free_flow_vehicle_minutes else None
    simulation_id = _simulation_id(
        MODEL_VERSION,
        order_at.isoformat(),
        seed,
        shelter_capacity_factor,
        include_fire_hazard,
        max_minutes,
        paradise_grid.grid()["data_version"],
        hazard_status.get("forecast_id", hazard_status["status"]),
    )
    return {
        "status": "simulated",
        "simulation_id": simulation_id,
        "model_version": MODEL_VERSION,
        "scenario": "evacuation",
        "order_at_utc": order_at.isoformat(),
        "order_at_local": paradise_replay.local_iso(order_at),
        "seed": seed,
        "grid_version": paradise_grid.grid()["grid_version"],
        "data_version": paradise_grid.grid()["data_version"],
        "shelter_capacity_factor": shelter_capacity_factor,
        "include_fire_hazard": include_fire_hazard,
        "fire_hazard": hazard_status,
        "summary": {
            "total_population": round(total_population, 1),
            "pre_evacuated_share": round(pre_evacuated_share, 4),
            "pre_evacuated_people": round(total_population * pre_evacuated_share, 1),
            "population_at_risk": round(total_population * (1.0 - pre_evacuated_share), 1),
            "assigned_population": round(sum(row.get("assigned_people", 0.0) for row in rows), 1),
            "unassigned_population": round(unassigned_people, 1),
            "evacuated_people": round(evacuated, 1),
            "un_evacuated_people": round(un_evacuated, 1),
            "unaccommodated_people": round(unaccommodated + unassigned_people, 1),
            "trapped_people": round(trapped, 1),
            "still_moving_people": round(still_moving + still_walking, 1),
            "clearance_status": "complete" if clearance_complete else "incomplete",
            "clearance_minutes": round(last_delivery, 1) if clearance_complete else None,
            "last_successful_arrival_minutes": round(last_delivery, 1) if evacuated > 0 else None,
            "max_simulation_minutes": max_minutes,
            "vehicle_minutes": round(vehicle_minutes, 1),
            "free_flow_vehicle_minutes": round(free_flow_vehicle_minutes, 1),
            "congestion_index": round(congestion, 3) if congestion is not None else None,
            "walking_people": round(sum(row.get("assigned_walking_people", 0.0) for row in rows), 1),
            "vehicle_people": round(sum(row.get("assigned_vehicle_people", 0.0) for row in rows), 1),
        },
        "shelters": list(shelter_state.values()),
        "timeline": timeline,
        "cell_flows": [
            {
                "cell_id": row["cell_id"],
                "population": round(row["remaining_population"], 1),
                "original_population": round(row["population"], 1),
                "assigned_shelter": row["shelter_id"],
                "assigned_people": round(row.get("assigned_people", 0.0), 1),
                "unassigned_people": round(row.get("unassigned_people", 0.0), 1),
                "departure_delay_minutes": row.get("departure_minute"),
                "path_length_cells": max(0, len(row.get("path", [])) - 1),
                "path_cell_ids": [cells[position]["id"] for position in row.get("path", [])],
                "distance_minutes": round(row["distance_minutes"], 1) if row["distance_minutes"] != math.inf else None,
            }
            for row in rows
        ],
        "assumptions": [
            "Population is aggregated 2013-2017 ACS exposure, not resident locations.",
            "Residents are synthetic agents generated from cell population. A scenario pre-evacuation share is removed before the modelled order time.",
            "Vehicle ownership, household size, departure delay and walking share are declared assumptions.",
            "Shelter locations and capacities are scenario reception areas outside the modeled grid, not official shelters.",
            "Road speed and capacity are assumptions on 2025 TIGER geometry; no live traffic or closures.",
            "Fire arrival comes from the uncalibrated forecast at the order time, not an observed perimeter.",
            "No public warning, evacuation order or dispatch is issued by this simulation.",
        ],
        "limitations": [
            "The model cannot predict real household behaviour or route choice.",
            "One-minute cell traversal and four-neighbour routing are coarse approximations.",
            "The shelter assignment is greedy and does not model dynamic rerouting.",
            "People are counted at cell level; no individual or address is used.",
            "Predicted fire arrival can be wrong; blocked edges are scenario consequences.",
            "Walkers use a straight-line travel estimate and a home-cell fire check; fire exposure along a pedestrian route is not represented.",
        ],
    }


def compare_evacuation(
    order_times: list[str] | None = None,
    *,
    seed: int = DEFAULT_SEED,
    shelter_capacity_factor: float = 1.0,
    include_fire_hazard: bool = True,
) -> dict[str, Any]:
    scenarios = config()["evacuation"].get("order_scenarios", [])
    selected = []
    if order_times:
        for index, value in enumerate(order_times):
            selected.append({"id": f"custom-{index + 1}", "at_utc": value, "label": value})
    else:
        selected = scenarios
    results = []
    for scenario in selected:
        result = simulate_evacuation(
            scenario["at_utc"],
            seed=seed,
            shelter_capacity_factor=shelter_capacity_factor,
            include_fire_hazard=include_fire_hazard,
        )
        results.append({
            "id": scenario.get("id"),
            "label": scenario.get("label"),
            "order_at_utc": result["order_at_utc"],
            "order_at_local": result["order_at_local"],
            "summary": result["summary"],
            "shelters": result["shelters"],
            "fire_hazard": result["fire_hazard"],
            "simulation_id": result["simulation_id"],
        })
    return {
        "status": "simulated",
        "scenario": "evacuation-order-comparison",
        "seed": seed,
        "shelter_capacity_factor": shelter_capacity_factor,
        "include_fire_hazard": include_fire_hazard,
        "scenarios": results,
        "comparison": [
            {
                "id": result["id"],
                "label": result["label"],
                "order_at_local": result["order_at_local"],
                "evacuated_people": result["summary"]["evacuated_people"],
                "un_evacuated_people": result["summary"]["un_evacuated_people"],
                "trapped_people": result["summary"]["trapped_people"],
                "clearance_status": result["summary"]["clearance_status"],
                "clearance_minutes": result["summary"]["clearance_minutes"],
                "last_successful_arrival_minutes": result["summary"]["last_successful_arrival_minutes"],
                "congestion_index": result["summary"]["congestion_index"],
            }
            for result in results
        ],
        "assumptions": [
            "All order times are scenario assumptions, not the actual Camp Fire order history.",
            "The same seed and base population are used, but later times also apply an assumed linear pre-evacuation share and may have different forecast availability; the comparison is not a causal estimate of an order-time effect.",
            "Shelters and capacities are simulated staging areas.",
        ],
    }


def simulate_resources(
    at_utc: str,
    *,
    lead_minutes: int = 120,
    strategy: str = "exposure_weighted",
) -> dict[str, Any]:
    if strategy not in {"exposure_weighted", "nearest_first", "none"}:
        raise ValueError("unknown resource strategy")
    at = paradise_replay.utc(at_utc)
    forecast = paradise_forecast.run_forecast(at.isoformat(), min(max(lead_minutes, 10), 720))
    resources = config()["resources"]
    simulation_id = _simulation_id(
        MODEL_VERSION,
        at.isoformat(),
        lead_minutes,
        strategy,
        forecast.get("forecast_id", forecast.get("status")),
        paradise_grid.grid()["data_version"],
    )
    if forecast.get("status") != "predicted":
        return {
            "status": "no_forecast",
            "simulation_id": simulation_id,
            "model_version": MODEL_VERSION,
            "grid_version": paradise_grid.grid()["grid_version"],
            "data_version": paradise_grid.grid()["data_version"],
            "reason": forecast.get("reason"),
            "at_utc": at.isoformat(),
            "strategy": strategy,
            "assignments": [],
            "summary": {"resources_used": 0, "protected_population": 0.0},
            "assumptions": resources.get("water_note"),
            "limitations": ["No forecast is available at this issue time; no resources are dispatched."],
        }
    cells = paradise_grid.cell_index()
    graph = road_graph()
    if strategy == "none":
        predicted_none = [item for item in forecast["cells"] if item["probability"] >= 0.5 and not item["seed"]]
        return {
            "status": "simulated",
            "simulation_id": simulation_id,
            "model_version": MODEL_VERSION,
            "grid_version": paradise_grid.grid()["grid_version"],
            "data_version": paradise_grid.grid()["data_version"],
            "scenario": "resource-allocation",
            "at_utc": at.isoformat(),
            "at_local": paradise_replay.local_iso(at),
            "lead_minutes": forecast["lead_minutes"],
            "strategy": strategy,
            "forecast_id": forecast["forecast_id"],
            "water_status": resources["water_status"],
            "water_note": resources["water_note"],
            "assignments": [],
            "summary": {
                "resources_used": 0,
                "resources_unassigned": len(resources["resources"]),
                "mean_response_minutes": None,
                "max_response_minutes": None,
                "protected_population": 0.0,
                "high_risk_cells": len(predicted_none),
                "untreated_high_risk_cells": len(predicted_none),
                "untreated_high_risk_population": round(sum(cells[item["cell_id"]]["population"] for item in predicted_none), 1),
            },
            "assumptions": [
                "No-action baseline for comparison only.",
                "No real dispatch, crew, aircraft or water source is represented.",
            ],
            "limitations": ["No resources are dispatched in this baseline."],
        }
    predicted = [item for item in forecast["cells"] if item["probability"] >= 0.3 and not item["seed"]]
    predicted.sort(key=lambda item: -(item["probability"] * (cells[item["cell_id"]]["population"] + 100)))
    home_cache: dict[str, tuple[dict[int, float], dict[int, int]]] = {}

    def travel_minutes(home_cell: str, target_cell: str, kind: str) -> float | None:
        home = cells[home_cell]
        target = cells[target_cell]
        if kind == "aircraft":
            distance_km = math.hypot(target["x_m"] - home["x_m"], target["y_m"] - home["y_m"]) / 1000.0
            return round(distance_km / 220.0 * 60.0, 1)
        home_node = graph["index"].get(home_cell)
        target_node = graph["index"].get(target_cell)
        if home_node is None or target_node is None:
            return None
        if home_cell not in home_cache:
            home_cache[home_cell] = dijkstra(home_node)
        distance = home_cache[home_cell][0].get(target_node, math.inf)
        return None if distance == math.inf else round(distance, 1)

    assignments = []
    used_targets = set()
    protected = 0.0
    for resource in resources["resources"]:
        candidates = []
        for item in predicted:
            if item["cell_id"] in used_targets:
                continue
            travel = travel_minutes(resource["home_cell_id"], item["cell_id"], resource["kind"])
            if travel is None:
                continue
            if strategy == "nearest_first":
                score = -travel
            elif strategy == "none":
                score = 0
            else:
                score = item["probability"] * (cells[item["cell_id"]]["population"] + 100)
            candidates.append((score, travel, item))
        if not candidates:
            assignments.append({
                "resource_id": resource["id"],
                "label": resource["label"],
                "kind": resource["kind"],
                "status": "unassigned",
                "reason": "no reachable high-risk untreated cell",
            })
            continue
        candidates.sort(key=lambda value: (-value[0], value[1], value[2]["cell_id"]))
        _, travel, target = candidates[0]
        used_targets.add(target["cell_id"])
        arrival = travel + resource["setup_minutes"]
        target_population = cells[target["cell_id"]]["population"]
        protected_people = target_population * target["probability"] * resource["effectiveness"]
        protected += protected_people
        assignments.append({
            "resource_id": resource["id"],
            "label": resource["label"],
            "kind": resource["kind"],
            "status": "assigned",
            "home_cell_id": resource["home_cell_id"],
            "target_cell_id": target["cell_id"],
            "target_probability": target["probability"],
            "travel_minutes": travel,
            "setup_minutes": resource["setup_minutes"],
            "arrival_minutes": round(arrival, 1),
            "task_end_minutes": round(arrival + resource["task_minutes"], 1),
            "effectiveness": resource["effectiveness"],
            "protected_population": round(protected_people, 1),
        })
    assigned = [item for item in assignments if item["status"] == "assigned"]
    response_times = [item["arrival_minutes"] for item in assigned]
    high_risk = [item for item in predicted if item["probability"] >= 0.5]
    untreated = [item for item in high_risk if item["cell_id"] not in used_targets]
    return {
        "status": "simulated",
        "simulation_id": simulation_id,
        "model_version": MODEL_VERSION,
        "grid_version": paradise_grid.grid()["grid_version"],
        "data_version": paradise_grid.grid()["data_version"],
        "scenario": "resource-allocation",
        "at_utc": at.isoformat(),
        "at_local": paradise_replay.local_iso(at),
        "lead_minutes": forecast["lead_minutes"],
        "strategy": strategy,
        "forecast_id": forecast["forecast_id"],
        "water_status": resources["water_status"],
        "water_note": resources["water_note"],
        "assignments": assignments,
        "summary": {
            "resources_used": len(assigned),
            "resources_unassigned": len(assignments) - len(assigned),
            "mean_response_minutes": round(sum(response_times) / len(response_times), 1) if response_times else None,
            "max_response_minutes": max(response_times) if response_times else None,
            "protected_population": round(protected, 1),
            "high_risk_cells": len(high_risk),
            "untreated_high_risk_cells": len(untreated),
            "untreated_high_risk_population": round(sum(cells[item["cell_id"]]["population"] for item in untreated), 1),
        },
        "assumptions": [
            "Firefighting units, home cells and effectiveness are simulated scenario values.",
            "No real dispatch, crew, aircraft or water source is represented.",
            "Travel uses the 500 m road graph, except aircraft use straight-line distance.",
            "Allocation uses predicted risk, aggregated population exposure and road access.",
            "Water availability is missing and cannot be claimed as a constraint that was met.",
        ],
        "limitations": [
            "No real resource positions, availability, travel times or outcomes are available.",
            "The protected-population number is an illustrative product of probability, population and assumed effectiveness.",
            "The model does not simulate suppression feedback on the fire spread.",
        ],
    }
