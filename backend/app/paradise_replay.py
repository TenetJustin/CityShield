"""Real Camp Fire replay built from frozen FIRMS observations and NIST windows.

The replay keeps three things separate:

* FIRMS detections are **observed** active-fire points.
* NIST map windows are **verified time constraints**; their spatial symbols are
  not digitized and are never synthesized.
* Cell aggregation is **derived** from the observed points.

The package is deterministic for a fixed data version and contains no synthetic
burn perimeter. A frame with no observation after a long gap says so.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from . import paradise_grid


DATA = paradise_grid.DATA
FIRMS_PATH = DATA / "camp_fire_firms_2018.json"
NIST_PATH = DATA / "camp_fire_nist_timeline.json"
PACIFIC = ZoneInfo("America/Los_Angeles")


def utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def local_iso(value: str | datetime) -> str:
    return utc(value).astimezone(PACIFIC).isoformat()


def local_label(value: str | datetime) -> str:
    return utc(value).astimezone(PACIFIC).strftime("%b %d, %Y %H:%M %Z")


@lru_cache(maxsize=1)
def firms_package() -> dict[str, Any]:
    return json.loads(FIRMS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def nist_package() -> dict[str, Any]:
    return json.loads(NIST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def detections() -> tuple[dict[str, Any], ...]:
    items = []
    for record in firms_package()["detections"]:
        acquired = utc(record["acquired_at"])
        cell = paradise_grid.cell_for_lonlat(record["longitude"], record["latitude"])
        items.append({
            "provider_record_id": record.get("provider_record_id"),
            "latitude": record["latitude"],
            "longitude": record["longitude"],
            "acquired_at": acquired.isoformat(),
            "acquired_at_local": acquired.astimezone(PACIFIC).isoformat(),
            "frp": record.get("frp"),
            "confidence": record.get("confidence"),
            "satellite": record.get("satellite"),
            "instrument": record.get("instrument"),
            "product": record.get("product"),
            "cell_id": cell["id"] if cell else None,
        })
    items.sort(
        key=lambda item: (
            item["acquired_at"],
            item["latitude"],
            item["longitude"],
            item["satellite"] or "",
            item["provider_record_id"] or "",
        )
    )
    return tuple(items)


@lru_cache(maxsize=1)
def frames() -> tuple[dict[str, Any], ...]:
    by_time: dict[str, list[dict[str, Any]]] = {}
    for item in detections():
        by_time.setdefault(item["acquired_at"], []).append(item)
    nist_windows = nist_package()["windows"]
    boundaries: dict[str, dict[str, Any]] = {}
    for window in nist_windows:
        for edge, kind in ((window["start_at"], "start"), (window["end_at"], "end")):
            key = utc(edge).isoformat()
            boundaries.setdefault(key, {"starts": [], "ends": []})
            boundaries[key][kind + "s"].append(window)

    all_times = sorted(set(by_time) | set(boundaries))
    first = all_times[0]
    first_dt = utc(first)
    cumulative_cells: set[str] = set()
    cumulative_detections = 0
    previous: str | None = None
    result = []
    for index, at in enumerate(all_times):
        at_dt = utc(at)
        new = by_time.get(at, [])
        new_cells = sorted({item["cell_id"] for item in new if item["cell_id"]})
        outside = sum(1 for item in new if not item["cell_id"])
        cumulative_cells.update(new_cells)
        cumulative_detections += len(new)
        boundary = boundaries.get(at, {"starts": [], "ends": []})
        active = next(
            (
                window
                for window in nist_windows
                if utc(window["start_at"]) <= at_dt < utc(window["end_at"])
            ),
            None,
        )
        if new and (boundary["starts"] or boundary["ends"]):
            kind = "firms-and-nist-boundary"
        elif new:
            kind = "firms-observation"
        elif boundary["starts"]:
            kind = "nist-window-start"
        elif boundary["ends"]:
            kind = "nist-window-end"
        else:
            kind = "nist-window"
        gap = None if previous is None else round((at_dt - utc(previous)).total_seconds() / 60.0, 1)
        if new:
            label = f"FIRMS snapshot · {len(new)} detections"
            data_status = "observed"
        elif boundary["starts"]:
            window = boundary["starts"][0]
            label = f"NIST window begins · {window['id']}"
            data_status = "verified-window"
        else:
            window = boundary["ends"][0]
            label = f"NIST window ends · {window['id']}"
            data_status = "verified-window"
        result.append({
            "id": f"frame-{index:02d}",
            "at_utc": at,
            "at_local": local_iso(at),
            "at_label": local_label(at),
            "minute_since_start": round((at_dt - first_dt).total_seconds() / 60.0, 1),
            "kind": kind,
            "label": label,
            "data_status": data_status,
            "observation_count": len(new),
            "cumulative_observation_count": cumulative_detections,
            "new_detections": new,
            "hotspot_cells": new_cells,
            "cumulative_detected_cells": sorted(cumulative_cells),
            "outside_grid_count": outside,
            "gap_since_previous_minutes": gap,
            "estimated": False,
            "nist_window": (
                {
                    "id": active["id"],
                    "start_at": active["start_at"],
                    "end_at": active["end_at"],
                    "source_url": active["source_url"],
                    "spatial_status": "not_digitized",
                }
                if active
                else None
            ),
            "nist_boundary": {
                "starts": [window["id"] for window in boundary["starts"]],
                "ends": [window["id"] for window in boundary["ends"]],
            },
            "weather": {
                "status": "missing",
                "reason": "No historical weather station record is in the frozen package.",
            },
            "observation_latency": {
                "status": "unknown",
                "reason": "FIRMS acquisition time is recorded; processing and availability latency are not recorded.",
            },
            "source_ids": ["nasa-firms"] if new else ["nist-timeline"],
        })
        previous = at
    return tuple(result)


@lru_cache(maxsize=1)
def replay_id() -> str:
    payload = {
        "event_id": firms_package()["event_id"],
        "data_version": paradise_grid.grid()["data_version"],
        "frames": [(frame["at_utc"], frame["kind"], frame["observation_count"]) for frame in frames()],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def frame_at(value: str | datetime) -> dict[str, Any]:
    """Return the latest real frame at or before a timestamp."""
    target = utc(value)
    selected = None
    for frame in frames():
        if utc(frame["at_utc"]) <= target:
            selected = frame
        else:
            break
    if selected is None:
        return frames()[0]
    return selected


def seed_cells_at(value: str | datetime) -> list[str]:
    target = utc(value)
    cells: set[str] = set()
    for item in detections():
        if utc(item["acquired_at"]) <= target and item["cell_id"]:
            cells.add(item["cell_id"])
    return sorted(cells)


def snapshot() -> dict[str, Any]:
    package = firms_package()
    quality = package["quality"]
    all_detections = detections()
    observation_frames = [frame for frame in frames() if frame["observation_count"] > 0]
    nist_windows = nist_package()["windows"]
    outside = sum(1 for item in all_detections if not item["cell_id"])
    max_gap = max(
        (
            frame["gap_since_previous_minutes"]
            for frame in frames()
            if frame["gap_since_previous_minutes"] is not None
        ),
        default=0,
    )
    return {
        "schema_version": "1.0",
        "replay_id": replay_id(),
        "event_id": package["event_id"],
        "area": package["area"],
        "timezone": "America/Los_Angeles",
        "grid_version": paradise_grid.grid()["grid_version"],
        "data_version": paradise_grid.grid()["data_version"],
        "sources": {
            "firms": {
                "owner": "NASA LANCE FIRMS",
                "status": "observed",
                "record_count": quality["record_count"],
                "unique_acquisition_times": quality["unique_acquisition_times"],
                "first_acquired_at": quality["first_acquired_at"],
                "last_acquired_at": quality["last_acquired_at"],
                "first_acquired_at_local": local_label(quality["first_acquired_at"]),
                "last_acquired_at_local": local_label(quality["last_acquired_at"]),
                "products": quality["products"],
                "satellites": quality["satellites"],
                "limitations": quality["limitations"],
            },
            "nist": {
                "owner": "National Institute of Standards and Technology",
                "status": "verified-window-only",
                "windows": len(nist_windows),
                "continuous_from": nist_package()["quality"]["continuous_from"],
                "continuous_to": nist_package()["quality"]["continuous_to"],
                "accepted_for_visual_validation": nist_package()["quality"]["accepted_for_visual_validation"],
                "accepted_for_model_scoring": nist_package()["quality"]["accepted_for_model_scoring"],
                "spatial_status": "not_digitized",
                "blocking_item": nist_package()["quality"]["blocking_item"],
            },
            "weather": {
                "status": "missing",
                "reason": "No historical weather observation is in the frozen package; a scenario assumption is used only by the forecast model.",
            },
            "population": {
                "status": "derived",
                "vintage": "2013-2017 ACS 5-year",
                "method": "area-weighted block groups",
            },
        },
        "frames": list(frames()),
        "summary": {
            "frame_count": len(frames()),
            "observation_frames": len(observation_frames),
            "nist_windows": len(nist_windows),
            "detections": len(all_detections),
            "cells_observed": len({item["cell_id"] for item in all_detections if item["cell_id"]}),
            "detections_outside_grid": outside,
            "first_frame_utc": frames()[0]["at_utc"],
            "first_observation_utc": observation_frames[0]["at_utc"] if observation_frames else None,
            "last_observation_utc": observation_frames[-1]["at_utc"] if observation_frames else None,
            "max_gap_minutes": max_gap,
            "observation_method": "FIRMS active-fire detections aggregated to 500 m cells; cumulative cells are a detection proxy, not a burn scar.",
        },
        "limits": [
            "FIRMS points are detections, not an authoritative perimeter.",
            "NIST map symbols are not digitized; NIST contributes time windows only.",
            "The first five hours of the fire have no mapped observations in this package.",
            "A 688-minute overnight gap is shown explicitly; no fake frames are inserted.",
            "Historical weather is missing; forecast weather is a declared scenario assumption.",
            "No resident locations or operational response records are present.",
        ],
    }


def quality_check() -> dict[str, Any]:
    package = snapshot()
    return {
        "status": "ready",
        "replay_id": package["replay_id"],
        "frames": package["summary"]["frame_count"],
        "observations": package["summary"]["detections"],
        "nist_spatial": "not_digitized",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
