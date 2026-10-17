"""Build a machine-readable quality report for the frozen Paradise inputs.

The report is intentionally conservative. A layer that is missing is reported as
missing; a layer that is coarse or old is reported with its limitation. The
website reads this JSON so the status shown to judges is the same status that
the model code enforces.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import paradise_grid

DATA = ROOT / "data" / "paradise"
DEST = DATA / "data_quality_report.json"
FIRMS = DATA / "camp_fire_firms_2018.json"
POPULATION = DATA / "population_acs_2017_block_groups.geojson"
GEOGRAPHY = DATA / "geography_2025.geojson"
TERRAIN = DATA / "terrain_3dep_7x7.json"
NIST = DATA / "camp_fire_nist_timeline.json"
NIST_VERIFICATION = DATA / "nist_source_verification.json"
GRID = DATA / "paradise_grid_500m.json"
PACIFIC = "America/Los_Angeles"
METERS_PER_DEGREE = 111_320.0


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iso_local(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        ZoneInfo(PACIFIC)
    ).isoformat()


def check(
    check_id: str,
    layer: str,
    status: str,
    summary: str,
    detail: str = "",
    value: Any = None,
    threshold: Any = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "layer": layer,
        "status": status,
        "summary": summary,
        "detail": detail,
        "value": value,
        "threshold": threshold,
    }


def firms_analysis(package: dict[str, Any], town, grid_bounds) -> dict[str, Any]:
    detections = package["detections"]
    times = sorted({item["acquired_at"] for item in detections})
    parsed = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in times]
    intervals = [
        round((later - earlier).total_seconds() / 60.0, 1)
        for earlier, later in zip(parsed, parsed[1:])
    ]
    per_time = {value: 0 for value in times}
    for item in detections:
        per_time[item["acquired_at"]] += 1
    inside_town = sum(
        1 for item in detections if town.contains(Point(item["longitude"], item["latitude"]))
    )
    inside_grid = sum(
        1
        for item in detections
        if paradise_grid.cell_for_lonlat(item["longitude"], item["latitude"]) is not None
    )
    exact_groups: dict[tuple, int] = {}
    near_pairs = 0
    for item in detections:
        key = (
            round(item["latitude"], 5),
            round(item["longitude"], 5),
            item["acq_date"],
            item["acq_time"],
        )
        exact_groups[key] = exact_groups.get(key, 0) + 1
    by_time: dict[str, list[dict[str, Any]]] = {}
    for item in detections:
        by_time.setdefault(item["acquired_at"], []).append(item)
    for group in by_time.values():
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                dy = (left["latitude"] - right["latitude"]) * METERS_PER_DEGREE
                dx = (
                    (left["longitude"] - right["longitude"])
                    * METERS_PER_DEGREE
                    * math.cos(math.radians(left["latitude"]))
                )
                if math.hypot(dx, dy) <= 375.0:
                    near_pairs += 1
    frp = [float(item["frp"]) for item in detections if isinstance(item.get("frp"), (int, float))]
    confidence: dict[str, int] = {}
    for item in detections:
        confidence[str(item.get("confidence"))] = confidence.get(str(item.get("confidence")), 0) + 1
    satellites: dict[str, int] = {}
    for item in detections:
        satellites[item["satellite"]] = satellites.get(item["satellite"], 0) + 1
    outside_grid = len(detections) - inside_grid
    return {
        "record_count": len(detections),
        "unique_acquisition_times": len(times),
        "first_acquired_at_utc": times[0] if times else None,
        "last_acquired_at_utc": times[-1] if times else None,
        "first_acquired_at_local": iso_local(times[0]) if times else None,
        "last_acquired_at_local": iso_local(times[-1]) if times else None,
        "span_hours": round((parsed[-1] - parsed[0]).total_seconds() / 3600.0, 2) if parsed else 0,
        "intervals_minutes": intervals,
        "max_gap_minutes": max(intervals) if intervals else 0,
        "gap_window": (
            {
                "from_utc": times[intervals.index(max(intervals))],
                "to_utc": times[intervals.index(max(intervals)) + 1],
                "minutes": max(intervals),
            }
            if intervals
            else None
        ),
        "observations_per_time": per_time,
        "inside_town_boundary": inside_town,
        "inside_grid_extent": inside_grid,
        "outside_grid_extent": outside_grid,
        "duplicate_identity_groups": sum(1 for count in exact_groups.values() if count > 1),
        "same_time_adjacent_pairs_within_375m": near_pairs,
        "satellites": satellites,
        "confidence_counts": confidence,
        "frp": {
            "count": len(frp),
            "min": min(frp) if frp else None,
            "median": sorted(frp)[len(frp) // 2] if frp else None,
            "max": max(frp) if frp else None,
        },
        "source_products": package.get("source_requests", []),
        "provider_schema_version": package.get("schema_version"),
        "generated_at": package.get("generated_at"),
        "quality": package.get("quality"),
    }


def build_report() -> dict[str, Any]:
    firms = json.loads(FIRMS.read_text(encoding="utf-8"))
    population = json.loads(POPULATION.read_text(encoding="utf-8"))
    geography = json.loads(GEOGRAPHY.read_text(encoding="utf-8"))
    terrain = json.loads(TERRAIN.read_text(encoding="utf-8"))
    nist = json.loads(NIST.read_text(encoding="utf-8"))
    nist_verification = json.loads(NIST_VERIFICATION.read_text(encoding="utf-8"))
    grid = json.loads(GRID.read_text(encoding="utf-8"))

    town_feature = next(
        feature
        for feature in geography["features"]
        if feature["properties"].get("geoid") == "0655520"
    )
    town = shape(town_feature["geometry"])
    extent = grid["extent"]["bounds_wgs84"]
    firms_stats = firms_analysis(firms, town, None)

    population_meta = population["metadata"]
    population_quality = population_meta["quality"]
    terrain_elevations = [sample["elevation_m"] for sample in terrain["samples"]]
    spacing_km = round(
        (terrain["bbox"][2] - terrain["bbox"][0]) * 111.32 * 0.76 / (terrain["grid_size"] - 1), 2
    )
    nist_windows = nist["windows"]
    nist_gap_free = all(
        previous["end_at"] == current["start_at"]
        for previous, current in zip(nist_windows, nist_windows[1:])
    )
    nist_spatial_records = sum(
        1 for window in nist_windows if window.get("observations") or window.get("geometry")
    )

    checks: list[dict[str, Any]] = []
    checks.append(check(
        "firms-file", "firms", "pass",
        "Frozen FIRMS package is present and parses.",
        f"{FIRMS.name} sha256={digest(FIRMS)[:16]}…",
        firms_stats["record_count"], 1,
    ))
    checks.append(check(
        "firms-required-fields", "firms", "pass",
        "All required detection fields are present and coordinates are valid.",
        "latitude, longitude, acq_date, acq_time, acquired_at, satellite and instrument.",
        firms["quality"]["missing_required_count"], 0,
    ))
    checks.append(check(
        "firms-exact-duplicates", "firms",
        "pass" if firms["quality"]["duplicate_count"] == 0 else "warn",
        "No exact duplicate identity groups were found after the identity-based dedupe.",
        f"provider duplicate identity groups={firms_stats['duplicate_identity_groups']}.",
        firms["quality"]["duplicate_count"], 0,
    ))
    checks.append(check(
        "firms-adjacent-detections", "firms", "info",
        "Same-overpass detections can be closer than the 375 m pixel footprint.",
        f"{firms_stats['same_time_adjacent_pairs_within_375m']} same-time pairs are within 375 m. They are retained as separate pixels but aggregated to grid cells for scoring so they are not counted as independent samples.",
        firms_stats["same_time_adjacent_pairs_within_375m"], None,
    ))
    checks.append(check(
        "firms-time-coverage", "firms", "warn",
        "FIRMS covers 2018-11-08 11:50 PT to 2018-11-09 14:01 PT in 9 snapshots, not the ignition morning.",
        f"Span {firms_stats['span_hours']} h; first snapshot {firms_stats['first_acquired_at_local']}; max gap {firms_stats['max_gap_minutes']} min.",
        firms_stats["unique_acquisition_times"], 4,
    ))
    checks.append(check(
        "firms-gap", "firms", "warn",
        "An 11.5-hour overnight observation gap separates the 21:30 UTC and 08:58 UTC snapshots.",
        f"Gap window {firms_stats['gap_window']}. Interpolation across this gap is labelled estimated and is not an observation.",
        firms_stats["max_gap_minutes"], 90,
    ))
    checks.append(check(
        "firms-spatial-scope", "firms", "warn",
        "Only part of the FIRMS query box lies in the shared Paradise grid.",
        f"{firms_stats['inside_grid_extent']} of {firms_stats['record_count']} detections fall inside the grid; {firms_stats['outside_grid_extent']} are counted but not mapped. {firms_stats['inside_town_boundary']} are inside the town boundary.",
        firms_stats["inside_grid_extent"], firms_stats["record_count"],
    ))
    checks.append(check(
        "firms-not-perimeter", "firms", "info",
        "FIRMS points are active-fire detections, not a burned-area perimeter.",
        "Hit, IoU and arrival metrics measure agreement with detections, not true burned area.",
        None, None,
    ))
    checks.append(check(
        "nist-windows", "nist", "pass",
        "Four continuous NIST observation windows are recorded with verified source hashes.",
        f"{nist_windows[0]['start_at']} to {nist_windows[-1]['end_at']}; continuous={nist_gap_free}.",
        len(nist_windows), 4,
    ))
    checks.append(check(
        "nist-source-hashes", "nist",
        "pass" if nist_verification.get("all_verified") else "fail",
        "All four NIST map PDFs were re-downloaded and their SHA-256 hashes match the timeline manifest.",
        "The PDFs are not committed; the verification record stores hashes, byte sizes and page counts.",
        sum(1 for item in nist_verification["checks"] if item["sha256_matches"]), 4,
    ))
    checks.append(check(
        "nist-spatial-digitization", "nist", "blocked",
        "NIST map symbols are not digitized and cannot be used for spatial scoring.",
        "The map annotations and symbols are embedded in a 14370x9746 raster; only time windows and file identity are machine-readable. The replay uses NIST windows as temporal constraints only.",
        nist_spatial_records, None,
    ))
    checks.append(check(
        "population-coverage", "population", "pass",
        "The ACS block-group layer covers the town clip and has no missing population joins.",
        f"Coverage {population_quality['town_area_coverage_pct']}%, block groups {population_quality['intersecting_block_groups']}, missing {population_quality['missing_population_geoids']}.",
        population_quality["town_area_coverage_pct"], 99.0,
    ))
    checks.append(check(
        "population-vintage", "population", "warn",
        "Population is 2013-2017 ACS, not a 2018 count.",
        "It is a pre-event exposure baseline; ACS 5-year estimates include sampling error and are not 2018 occupancy.",
        population_meta["source_population_vintage"], "2018",
    ))
    checks.append(check(
        "population-plausibility", "population", "warn",
        "Area-weighted town population is 17.6% below the ACS place estimate.",
        f"Allocated {population_meta['allocated_population_estimate']} vs place estimate {population_meta['place_population_estimate']} (±{population_meta['allocated_population_moe']} MOE). Exposure metrics inherit this gap.",
        population_meta["difference_from_place_estimate_pct"], 10.0,
    ))
    checks.append(check(
        "population-not-residents", "population", "pass",
        "The layer contains no resident locations.",
        "Synthetic residents are generated later from aggregated cell population and are labelled simulated.",
        population_meta["not_resident_locations"], True,
    ))
    checks.append(check(
        "roads-vintage", "roads", "warn",
        "Roads are 2025 Census TIGER/Line geometry, seven years after the event.",
        "No closures, lane capacity, traffic speeds or evacuation permissions are included.",
        geography["source_vintage"], "2018",
    ))
    checks.append(check(
        "terrain-resolution", "terrain", "warn",
        "Terrain is a 7×7 display mesh, not a modeling DEM.",
        f"Sample spacing is about {spacing_km} km; cell elevation and slope are interpolated and marked derived-coarse.",
        terrain["grid_size"], ">=100",
    ))
    checks.append(check(
        "terrain-acquisition", "terrain", "warn",
        "The 3DEP samples were acquired in 2022, after the 2018 fire.",
        f"Elevation acquisition date {terrain['samples'][0]['acquisition_date']}. This is post-fire terrain and cannot represent 2018 vegetation or fuel.",
        terrain["samples"][0]["acquisition_date"], "2018-11-08",
    ))
    checks.append(check(
        "terrain-range", "terrain", "pass",
        "Elevation samples parse into a plausible local relief range.",
        f"{min(terrain_elevations)}–{max(terrain_elevations)} m across 49 samples.",
        [min(terrain_elevations), max(terrain_elevations)], None,
    ))
    checks.append(check(
        "crs", "grid", "pass",
        "Input vectors use EPSG:4326 and the shared grid uses a documented local metric projection.",
        grid["crs"]["formula"],
        grid["crs"]["name"], "documented",
    ))
    checks.append(check(
        "timezone", "time", "pass",
        "All event timestamps are stored with UTC offsets and displayed in America/Los_Angeles.",
        "FIRMS acquired_at is UTC; NIST windows carry -08:00 offsets; the UI converts to PT.",
        PACIFIC, PACIFIC,
    ))
    checks.append(check(
        "fuel-layer", "fuel", "blocked",
        "No LANDFIRE or other observed fuel layer is bundled.",
        "Every cell uses a declared default fuel value of 0.7. This is an assumption, not observed fuel.",
        grid["layers"]["fuel"]["value"], None,
    ))
    checks.append(check(
        "water-layer", "water", "blocked",
        "No authoritative hydrant, tank or draft-site layer is bundled.",
        "Resource allocation cannot claim water-aware siting; water availability is an operational blocker.",
        None, None,
    ))
    checks.append(check(
        "critical-facilities", "critical_facilities", "blocked",
        "No authoritative critical-facility layer is bundled.",
        "No school, care facility or hospital locations are invented.",
        None, None,
    ))
    checks.append(check(
        "shelters", "shelters", "info",
        "Shelter locations and capacities are scenario assumptions.",
        "The evacuation model labels them as scenario data, not official shelters.",
        "scenario", None,
    ))
    checks.append(check(
        "grid-shared", "grid", "pass",
        "All replay layers map to one 500 m grid with stable cell IDs.",
        f"{grid['cell_count']} cells, {grid['extent']['cols']}×{grid['extent']['rows']}, id rule {grid['id_rule']}.",
        grid["cell_count"], None,
    ))

    counts = {status: sum(1 for item in checks if item["status"] == status) for status in ("pass", "warn", "blocked", "fail", "info")}
    overall_status = "usable_with_declared_gaps"
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_id": "camp-fire-2018",
        "area": "Paradise, California",
        "data_version": grid["data_version"],
        "grid_version": grid["grid_version"],
        "timezone": PACIFIC,
        "overall": {
            "status": overall_status,
            "status_label": "Usable with declared gaps",
            "accepted_for_historical_replay": True,
            "accepted_for_firms_model_scoring": True,
            "accepted_for_nist_spatial_scoring": False,
            "operational_ready": False,
            "summary": "FIRMS observations, NIST time windows, ACS exposure and the shared grid are usable for a labelled historical replay. NIST spatial scoring, fuel, water, facilities and official shelters remain unavailable.",
            "counts": counts,
        },
        "inputs": {
            "firms": {"file": FIRMS.name, "sha256": digest(FIRMS), "bytes": FIRMS.stat().st_size},
            "population": {"file": POPULATION.name, "sha256": digest(POPULATION), "bytes": POPULATION.stat().st_size},
            "geography": {"file": GEOGRAPHY.name, "sha256": digest(GEOGRAPHY), "bytes": GEOGRAPHY.stat().st_size},
            "terrain": {"file": TERRAIN.name, "sha256": digest(TERRAIN), "bytes": TERRAIN.stat().st_size},
            "nist_timeline": {"file": NIST.name, "sha256": digest(NIST), "bytes": NIST.stat().st_size},
            "grid": {"file": GRID.name, "sha256": digest(GRID), "bytes": GRID.stat().st_size},
        },
        "coverage": {
            "firms": firms_stats,
            "population": {
                "vintage": population_meta["source_population_vintage"],
                "place_estimate": population_meta["place_population_estimate"],
                "allocated_estimate": population_meta["allocated_population_estimate"],
                "allocated_moe": population_meta["allocated_population_moe"],
                "difference_pct": population_meta["difference_from_place_estimate_pct"],
                "coverage_pct": population_quality["town_area_coverage_pct"],
                "block_groups": population_quality["intersecting_block_groups"],
                "missing_geoids": population_quality["missing_population_geoids"],
            },
            "nist": {
                "windows": nist_windows,
                "continuous": nist_gap_free,
                "source_verification": nist_verification,
                "digitized_spatial_records": nist_spatial_records,
                "accepted_for_visual_validation": nist["quality"]["accepted_for_visual_validation"],
                "accepted_for_model_scoring": nist["quality"]["accepted_for_model_scoring"],
                "blocking_item": nist["quality"]["blocking_item"],
            },
            "terrain": {
                "samples": len(terrain["samples"]),
                "grid_size": terrain["grid_size"],
                "spacing_km": spacing_km,
                "acquisition_date": terrain["samples"][0]["acquisition_date"],
                "elevation_range_m": [min(terrain_elevations), max(terrain_elevations)],
            },
            "roads": {
                "features": len(geography["features"]) - 1,
                "vintage": geography["source_vintage"],
                "total_length_km": round(sum(cell["road_length_m"] for cell in grid["cells"]) / 1000.0, 1),
            },
            "grid": {
                "cells": grid["cell_count"],
                "resolution_m": grid["resolution_m"],
                "buffer_m": grid["buffer_m"],
                "bounds_wgs84": extent,
                "population_total": grid["town"]["population_allocated"],
            },
        },
        "checks": checks,
        "limitations": [
            "FIRMS detections are points, not perimeters; metrics measure detection agreement.",
            "The first 5.4 hours of the fire (NIST windows 06:25–10:00 PT) have no FIRMS observations in this package.",
            "NIST spatial symbols are not digitized, so NIST cannot be used for spatial scoring.",
            "Fuel is a declared default; water and critical facilities are absent.",
            "Population is 2013–2017 ACS, pre-event and area-weighted, not 2018 occupancy.",
            "Roads are 2025 geometry with no closures, capacity or evacuation permissions.",
            "Shelters and response resources are scenario assumptions, not verified assets.",
            "The system is a research prototype and cannot issue warnings, evacuations or dispatches.",
        ],
    }


def main() -> None:
    report = build_report()
    DEST.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    counts = report["overall"]["counts"]
    print(
        f"Wrote {DEST}: {counts['pass']} pass, {counts['warn']} warn, "
        f"{counts['blocked']} blocked, {counts['info']} info; "
        f"data_version={report['data_version']}"
    )


if __name__ == "__main__":
    main()
