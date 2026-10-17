"""Build the frozen, shared 500 m Paradise grid used by every replay view.

The grid is a local equirectangular metric grid anchored at the configured
origin. It is deliberately *not* presented as an EPSG projected CRS: the
formula is documented in the artifact and the app uses the same formula for
point-to-cell lookup. No shapely dependency is needed at runtime.

Inputs are the frozen FIRMS, ACS/TIGER, Census geography and USGS 3DEP display
samples. Every cell records the source and method for each attribute. Missing
layers (fuel, water, facilities) are marked, never silently invented.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import box, mapping, shape
from shapely.ops import transform
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "paradise"
CONFIG_PATH = ROOT / "config" / "paradise_replay.json"
DEST = DATA / "paradise_grid_500m.json"

GEOGRAPHY = DATA / "geography_2025.geojson"
POPULATION = DATA / "population_acs_2017_block_groups.geojson"
TERRAIN = DATA / "terrain_3dep_7x7.json"
FIRMS = DATA / "camp_fire_firms_2018.json"
NIST = DATA / "camp_fire_nist_timeline.json"
TOWN_GEOID = "0655520"

CELL_SIDE_M = 500.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_version(config: dict[str, Any]) -> tuple[str, dict[str, str]]:
    hashes = {
        path.name: sha256(path)
        for path in (GEOGRAPHY, POPULATION, TERRAIN, FIRMS, NIST)
    }
    canonical = json.dumps(
        {"grid": config["grid"], "hashes": hashes}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16], hashes


def projector(config: dict[str, Any]):
    grid = config["grid"]
    origin_lon = float(grid["origin"]["longitude"])
    origin_lat = float(grid["origin"]["latitude"])
    m_per_lon = float(grid["meters_per_degree_longitude"])
    m_per_lat = float(grid["meters_per_degree_latitude"])

    def forward(lon: float, lat: float, z: float | None = None):
        return ((lon - origin_lon) * m_per_lon, (lat - origin_lat) * m_per_lat)

    def inverse(x: float, y: float, z: float | None = None):
        return (origin_lon + x / m_per_lon, origin_lat + y / m_per_lat)

    return forward, inverse


def local_geometry(geometry, forward):
    return transform(lambda x, y, z=None: forward(x, y), geometry)


def wgs84_geometry(geometry, inverse):
    return transform(lambda x, y, z=None: inverse(x, y), geometry)


def bilinear_terrain(terrain: dict[str, Any], lon: float, lat: float) -> float:
    """Interpolate the 7x7 USGS display samples; clamp outside the sample box."""
    west, south, east, north = terrain["bbox"]
    size = int(terrain["grid_size"])
    values = {(point["row"], point["col"]): point["elevation_m"] for point in terrain["samples"]}
    row = (north - lat) / (north - south) * (size - 1) if north != south else 0.0
    col = (lon - west) / (east - west) * (size - 1) if east != west else 0.0
    row = max(0.0, min(size - 1.000001, row))
    col = max(0.0, min(size - 1.000001, col))
    r0, c0 = int(math.floor(row)), int(math.floor(col))
    fr, fc = row - r0, col - c0
    at = lambda r, c: values[(r, c)]
    return (
        at(r0, c0) * (1 - fr) * (1 - fc)
        + at(r0 + 1, c0) * fr * (1 - fc)
        + at(r0, c0 + 1) * (1 - fr) * fc
        + at(r0 + 1, c0 + 1) * fr * fc
    )


def build(config: dict[str, Any]) -> dict[str, Any]:
    forward, inverse = projector(config)
    grid_cfg = config["grid"]
    resolution = float(grid_cfg["resolution_m"])
    buffer_m = float(grid_cfg["buffer_m"])

    geography = json.loads(GEOGRAPHY.read_text(encoding="utf-8"))
    population = json.loads(POPULATION.read_text(encoding="utf-8"))
    terrain = json.loads(TERRAIN.read_text(encoding="utf-8"))

    town = shape(next(
        feature["geometry"]
        for feature in geography["features"]
        if feature["properties"].get("geoid") == TOWN_GEOID
    ))
    town_local = local_geometry(town, forward)
    buffered_local = town_local.buffer(buffer_m)
    buffered = wgs84_geometry(buffered_local, inverse)

    min_x = math.floor(buffered_local.bounds[0] / resolution) * resolution
    min_y = math.floor(buffered_local.bounds[1] / resolution) * resolution
    max_x = math.ceil(buffered_local.bounds[2] / resolution) * resolution
    max_y = math.ceil(buffered_local.bounds[3] / resolution) * resolution
    cols = int(round((max_x - min_x) / resolution))
    rows = int(round((max_y - min_y) / resolution))

    cell_polygons: list[Any] = []
    cell_meta: list[dict[str, Any]] = []
    for row in range(rows):
        for col in range(cols):
            x0 = min_x + col * resolution
            y0 = min_y + row * resolution
            polygon = box(x0, y0, x0 + resolution, y0 + resolution)
            cell_polygons.append(polygon)
            cell_meta.append({"row": row, "col": col, "x0": x0, "y0": y0})

    tree = STRtree(cell_polygons)
    road_lengths: list[dict[str, float]] = [
        {"total": 0.0, "major": 0.0} for _ in cell_polygons
    ]
    road_names: list[list[tuple[float, str]]] = [[] for _ in cell_polygons]
    for feature in geography["features"]:
        if feature["properties"].get("kind") == "town_boundary":
            continue
        road = local_geometry(shape(feature["geometry"]), forward)
        if road.is_empty:
            continue
        name = feature["properties"].get("name") or "Unnamed road"
        mtfcc = feature["properties"].get("mtfcc")
        for index in tree.query(road):
            overlap = road.intersection(cell_polygons[index])
            if overlap.is_empty:
                continue
            length = overlap.length
            road_lengths[index]["total"] += length
            if mtfcc in {"S1100", "S1200"}:
                road_lengths[index]["major"] += length
            road_names[index].append((length, name))

    block_groups = []
    for feature in population["features"]:
        geometry = local_geometry(shape(feature["geometry"]), forward)
        if geometry.is_empty or geometry.area <= 0:
            continue
        block_groups.append({
            "geoid": feature["properties"]["geoid"],
            "geometry": geometry,
            "population": float(feature["properties"]["allocated_population"]),
            "moe": float(feature["properties"].get("allocated_population_moe") or 0.0),
        })
    bg_tree = STRtree([item["geometry"] for item in block_groups])
    bg_areas = [item["geometry"].area for item in block_groups]

    population_values: list[float] = []
    population_moes: list[float] = []
    for polygon in cell_polygons:
        total = 0.0
        moe_squares = 0.0
        for index in bg_tree.query(polygon):
            overlap = polygon.intersection(block_groups[index]["geometry"])
            if overlap.is_empty:
                continue
            share = overlap.area / bg_areas[index] if bg_areas[index] else 0.0
            total += block_groups[index]["population"] * share
            moe_squares += (block_groups[index]["moe"] * share) ** 2
        population_values.append(total)
        population_moes.append(math.sqrt(moe_squares))

    cells = []
    total_population = 0.0
    for index, meta in enumerate(cell_meta):
        polygon = cell_polygons[index]
        x0, y0 = meta["x0"], meta["y0"]
        cx, cy = x0 + resolution / 2, y0 + resolution / 2
        lon, lat = inverse(cx, cy)
        town_fraction = polygon.intersection(town_local).area / polygon.area
        elevation = bilinear_terrain(terrain, lon, lat)
        dx = bilinear_terrain(terrain, *inverse(cx + resolution / 2, cy)) - bilinear_terrain(
            terrain, *inverse(cx - resolution / 2, cy)
        )
        dy = bilinear_terrain(terrain, *inverse(cx, cy + resolution / 2)) - bilinear_terrain(
            terrain, *inverse(cx, cy - resolution / 2)
        )
        gradient = math.hypot(dx, dy) / resolution
        slope_deg = math.degrees(math.atan(gradient))
        population = population_values[index]
        total_population += population
        names = sorted(road_names[index], key=lambda item: -item[0])
        unique_names = []
        for _, name in names:
            if name not in unique_names:
                unique_names.append(name)
            if len(unique_names) >= 4:
                break
        cell_id = f"P-{meta['row']:02d}-{meta['col']:02d}"
        west, south = inverse(x0, y0)
        east, north = inverse(x0 + resolution, y0 + resolution)
        cells.append({
            "id": cell_id,
            "row": meta["row"],
            "col": meta["col"],
            "centroid": {"longitude": round(lon, 6), "latitude": round(lat, 6)},
            "bounds_wgs84": {
                "west": round(west, 6),
                "south": round(south, 6),
                "east": round(east, 6),
                "north": round(north, 6),
            },
            "x_m": round(cx, 1),
            "y_m": round(cy, 1),
            "size_m": resolution,
            "in_town": town_fraction > 0.0,
            "town_fraction": round(town_fraction, 4),
            "elevation_m": round(elevation, 1),
            "slope_deg": round(slope_deg, 2),
            "slope_norm": round(min(1.0, gradient / 1.0), 3),
            "population": round(population, 2),
            "population_moe": round(population_moes[index], 2),
            "road_length_m": round(road_lengths[index]["total"], 1),
            "major_road_length_m": round(road_lengths[index]["major"], 1),
            "road_names": unique_names,
            "fuel_value": float(config["forecast"]["fuel_default"]),
            "sources": {
                "population": "2013-2017 ACS 5-year block groups, area-weighted to the town clip",
                "elevation": "USGS 3DEP 7x7 display samples, bilinear interpolation",
                "slope": "gradient of the interpolated 7x7 elevation samples",
                "roads": "2025 TIGER/Line road intersection length",
                "fuel": "assumed default; no LANDFIRE fuel layer in this build",
            },
            "status": {
                "population": "derived",
                "elevation": "derived-coarse",
                "slope": "derived-coarse",
                "roads": "observed",
                "fuel": "assumed",
                "water": "missing",
                "critical_facilities": "missing",
            },
        })

    version, hashes = data_version(config)
    town_area_km2 = town_local.area / 1_000_000
    buffered_bounds = buffered.bounds
    return {
        "schema_version": "1.0",
        "grid_version": "paradise-500m-v1",
        "data_version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_id": config["event_id"],
        "resolution_m": resolution,
        "buffer_m": buffer_m,
        "cell_count": len(cells),
        "crs": {
            "name": grid_cfg["crs"],
            "type": "local tangent-plane equirectangular grid, metric",
            "units": "meters",
            "origin": grid_cfg["origin"],
            "meters_per_degree_latitude": grid_cfg["meters_per_degree_latitude"],
            "meters_per_degree_longitude": grid_cfg["meters_per_degree_longitude"],
            "formula": "x_m=(lon-origin.longitude)*meters_per_degree_longitude; y_m=(lat-origin.latitude)*meters_per_degree_latitude",
            "warning": "This is a documented local grid, not EPSG:32610 or an official survey datum.",
        },
        "id_rule": grid_cfg["id_rule"],
        "town": {
            "name": "Paradise, California",
            "geoid": TOWN_GEOID,
            "area_km2": round(town_area_km2, 3),
            "bounds_wgs84": [round(value, 6) for value in town.bounds],
            "boundary": mapping(town.simplify(0.00005, preserve_topology=True)),
            "population_vintage": "2013-2017 ACS 5-year",
            "population_allocated": round(total_population, 2),
        },
        "extent": {
            "x_min_m": min_x,
            "x_max_m": max_x,
            "y_min_m": min_y,
            "y_max_m": max_y,
            "cols": cols,
            "rows": rows,
            "bounds_wgs84": {
                "west": round(buffered_bounds[0], 6),
                "south": round(buffered_bounds[1], 6),
                "east": round(buffered_bounds[2], 6),
                "north": round(buffered_bounds[3], 6),
            },
        },
        "source_hashes": hashes,
        "layers": {
            "population": {
                "status": "derived",
                "source": "Census 2017 TIGER block groups + 2013-2017 ACS 5-year",
                "method": "block-group population multiplied by the cell overlap fraction of the town-clipped block group",
                "limitations": [
                    "Area weighting assumes uniform population within each block group.",
                    "ACS estimates carry sampling error; the layer has no addresses or live occupancy.",
                ],
            },
            "roads": {
                "status": "observed",
                "source": "2025 Census TIGER/Line roads",
                "method": "intersection length of road segments with each cell",
                "limitations": [
                    "2025 geometry is not the 2018 evacuation network.",
                    "No closures, lane capacity, traffic speed or evacuation permission is included.",
                ],
            },
            "elevation": {
                "status": "derived-coarse",
                "source": "USGS 3DEP elevation point query, 7x7 samples",
                "method": "bilinear interpolation and local gradient",
                "limitations": [
                    "The 7x7 sample mesh is display-only and is not a modeling DEM.",
                    "Slope is a coarse derived value and must not be treated as surveyed terrain.",
                ],
            },
            "fuel": {
                "status": "assumed",
                "value": float(config["forecast"]["fuel_default"]),
                "source": "No LANDFIRE fuel layer is bundled.",
                "method": "documented default used by the transparent spread model",
                "limitations": ["Fuel is not observed for any cell."],
            },
            "water": {
                "status": "missing",
                "reason": "No authoritative hydrant, tank or draft-site layer is bundled.",
            },
            "critical_facilities": {
                "status": "missing",
                "reason": "No authoritative critical-facility layer is bundled.",
            },
            "shelters": {
                "status": "scenario",
                "reason": "Shelter locations and capacities are scenario assumptions, not official shelters.",
            },
        },
        "cells": cells,
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    artifact = build(config)
    DEST.write_text(json.dumps(artifact, separators=(",", ":")), encoding="utf-8")
    population = sum(cell["population"] for cell in artifact["cells"])
    roads = sum(cell["road_length_m"] for cell in artifact["cells"]) / 1000
    print(
        f"Wrote {DEST} with {artifact['cell_count']} cells "
        f"({artifact['extent']['cols']}x{artifact['extent']['rows']}), "
        f"population={population:.1f}, roads={roads:.1f} km, "
        f"data_version={artifact['data_version']}"
    )


if __name__ == "__main__":
    main()
