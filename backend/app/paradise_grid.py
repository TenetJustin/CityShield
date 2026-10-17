"""Shared Paradise grid, replay configuration and data-quality report.

Every Paradise view and model imports this module instead of deriving its own
grid. The frozen artifact is built by scripts/build_paradise_grid.py; runtime
code only reads JSON, so it has no shapely dependency and runs on LinuxONE.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "paradise"
GRID_PATH = DATA / "paradise_grid_500m.json"
QUALITY_PATH = DATA / "data_quality_report.json"
CONFIG_PATH = ROOT / "config" / "paradise_replay.json"


@lru_cache(maxsize=1)
def replay_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def grid() -> dict[str, Any]:
    artifact = json.loads(GRID_PATH.read_text(encoding="utf-8"))
    validate_grid(artifact)
    return artifact


@lru_cache(maxsize=1)
def cell_index() -> dict[str, dict[str, Any]]:
    return {cell["id"]: cell for cell in grid()["cells"]}


@lru_cache(maxsize=1)
def data_quality() -> dict[str, Any]:
    if not QUALITY_PATH.exists():
        return {
            "status": "not_built",
            "path": str(QUALITY_PATH.relative_to(ROOT)),
            "reason": "Run scripts/build_paradise_data_quality.py.",
        }
    return json.loads(QUALITY_PATH.read_text(encoding="utf-8"))


def validate_grid(artifact: dict[str, Any]) -> None:
    required = {"cell_count", "resolution_m", "extent", "crs", "cells", "data_version"}
    missing = required - set(artifact)
    if missing:
        raise ValueError(f"grid artifact missing: {sorted(missing)}")
    cells = artifact["cells"]
    if len(cells) != artifact["cell_count"]:
        raise ValueError("grid cell_count does not match cells")
    ids = [cell["id"] for cell in cells]
    if len(ids) != len(set(ids)):
        raise ValueError("grid cell ids are not unique")
    for cell in cells:
        if cell["size_m"] != artifact["resolution_m"]:
            raise ValueError(f"cell {cell['id']} has inconsistent size")
        for key in ("population", "elevation_m", "slope_norm", "road_length_m"):
            if not isinstance(cell.get(key), (int, float)):
                raise ValueError(f"cell {cell['id']} missing numeric {key}")
        if "sources" not in cell or "status" not in cell:
            raise ValueError(f"cell {cell['id']} missing provenance")


def cell_id_for(row: int, col: int) -> str:
    return f"P-{row:02d}-{col:02d}"


def cell_for_lonlat(longitude: float, latitude: float) -> dict[str, Any] | None:
    """Map WGS84 coordinates to the shared grid using the documented formula."""
    artifact = grid()
    crs = artifact["crs"]
    extent = artifact["extent"]
    x = (longitude - crs["origin"]["longitude"]) * crs["meters_per_degree_longitude"]
    y = (latitude - crs["origin"]["latitude"]) * crs["meters_per_degree_latitude"]
    resolution = artifact["resolution_m"]
    col = math.floor((x - extent["x_min_m"]) / resolution)
    row = math.floor((y - extent["y_min_m"]) / resolution)
    if not (0 <= row < extent["rows"] and 0 <= col < extent["cols"]):
        return None
    return cell_index().get(cell_id_for(row, col))


def cell_for_point(longitude: float, latitude: float) -> dict[str, Any] | None:
    return cell_for_lonlat(longitude, latitude)


def cell_ids_for_points(points: list[tuple[float, float]]) -> tuple[list[str], int]:
    """Return unique cell ids and the count of points outside the grid."""
    ids: set[str] = set()
    outside = 0
    for longitude, latitude in points:
        cell = cell_for_lonlat(longitude, latitude)
        if cell is None:
            outside += 1
        else:
            ids.add(cell["id"])
    return sorted(ids), outside


def exposure_summary() -> dict[str, Any]:
    artifact = grid()
    cells = artifact["cells"]
    inside = [cell for cell in cells if cell["in_town"]]
    return {
        "total_population": round(sum(cell["population"] for cell in cells), 2),
        "cells_with_population": sum(1 for cell in cells if cell["population"] > 0),
        "town_cells": len(inside),
        "town_population": round(sum(cell["population"] for cell in inside), 2),
        "population_vintage": artifact["town"]["population_vintage"],
        "population_moe_total": round(
            math.sqrt(sum(cell["population_moe"] ** 2 for cell in cells)), 2
        ),
        "method": artifact["layers"]["population"]["method"],
        "limitations": artifact["layers"]["population"]["limitations"],
        "data_version": artifact["data_version"],
        "status": "derived",
    }


def grid_summary() -> dict[str, Any]:
    artifact = grid()
    report = data_quality()
    return {
        "grid_version": artifact["grid_version"],
        "data_version": artifact["data_version"],
        "event_id": artifact["event_id"],
        "resolution_m": artifact["resolution_m"],
        "buffer_m": artifact["buffer_m"],
        "cell_count": artifact["cell_count"],
        "cols": artifact["extent"]["cols"],
        "rows": artifact["extent"]["rows"],
        "bounds_wgs84": artifact["extent"]["bounds_wgs84"],
        "town": {key: artifact["town"][key] for key in ("name", "geoid", "area_km2", "bounds_wgs84", "population_vintage", "population_allocated")},
        "crs": artifact["crs"],
        "id_rule": artifact["id_rule"],
        "layers": artifact["layers"],
        "exposure": exposure_summary(),
        "quality": {
            "status": report.get("overall", {}).get("status", "not_built"),
            "status_label": report.get("overall", {}).get("status_label", "Not built"),
            "counts": report.get("overall", {}).get("counts", {}),
        },
    }
