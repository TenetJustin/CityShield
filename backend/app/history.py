"""Build and inspect frozen Paradise historical observation packages."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARADISE_FIRMS_HISTORY = ROOT / "data" / "paradise" / "camp_fire_firms_2018.json"
PARADISE_POPULATION = ROOT / "data" / "paradise" / "population_acs_2017_block_groups.geojson"
REQUIRED_DETECTION_FIELDS = (
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "acquired_at",
    "satellite",
    "instrument",
)


def detection_identity(record: dict[str, Any]) -> str:
    canonical = "|".join(
        str(record.get(field, ""))
        for field in ("latitude", "longitude", "acq_date", "acq_time", "satellite")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def profile_firms_detections(records: list[dict[str, Any]]) -> dict[str, Any]:
    identities = [detection_identity(record) for record in records]
    unique_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    missing_required = 0
    invalid_coordinates = 0

    for record, identity in zip(records, identities):
        if identity in seen:
            duplicate_count += 1
            continue
        seen.add(identity)
        item = {**record, "provider_record_id": identity}
        if any(item.get(field) in (None, "") for field in REQUIRED_DETECTION_FIELDS):
            missing_required += 1
        latitude = item.get("latitude")
        longitude = item.get("longitude")
        if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
            invalid_coordinates += 1
        if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
            invalid_coordinates += 1
        unique_records.append(item)

    timestamps = sorted(
        {record["acquired_at"] for record in unique_records if record.get("acquired_at")}
    )
    products = sorted({record.get("product") for record in unique_records if record.get("product")})
    satellites = sorted(
        {record.get("satellite") for record in unique_records if record.get("satellite")}
    )
    accepted = bool(unique_records) and len(timestamps) >= 4 and not missing_required and not invalid_coordinates
    return {
        "detections": unique_records,
        "quality": {
            "raw_record_count": len(records),
            "record_count": len(unique_records),
            "duplicate_count": duplicate_count,
            "missing_required_count": missing_required,
            "invalid_coordinate_count": invalid_coordinates,
            "unique_acquisition_times": len(timestamps),
            "first_acquired_at": timestamps[0] if timestamps else None,
            "last_acquired_at": timestamps[-1] if timestamps else None,
            "products": products,
            "satellites": satellites,
            "minimum_replay_snapshots": 4,
            "accepted_for_replay": accepted,
            "limitations": [
                "Satellite detections are observation points, not authoritative fire perimeters.",
                "Cloud, smoke, scan timing and sensor coverage can create observation gaps.",
                "Historical detections must be evaluated against an independent progression source.",
            ],
        },
    }


def build_firms_history_package(
    records: list[dict[str, Any]],
    *,
    source_requests: list[dict[str, Any]],
    bounds: dict[str, float],
) -> dict[str, Any]:
    profile = profile_firms_detections(records)
    return {
        "schema_version": "1.0",
        "event_id": "camp-fire-2018",
        "area": "Paradise, California",
        "data_mode": "historical-replay",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_owner": "NASA LANCE FIRMS",
        "source_url": "https://firms.modaps.eosdis.nasa.gov/api/area/",
        "source_requests": source_requests,
        "bounds_wgs84": bounds,
        "quality": profile["quality"],
        "detections": profile["detections"],
    }


def load_firms_history() -> dict[str, Any]:
    if not PARADISE_FIRMS_HISTORY.exists():
        return {
            "status": "not_built",
            "path": str(PARADISE_FIRMS_HISTORY.relative_to(ROOT)),
            "reason": "Run scripts/build_paradise_firms_history.py with FIRMS_MAP_KEY configured.",
            "accepted_for_replay": False,
        }
    package = json.loads(PARADISE_FIRMS_HISTORY.read_text(encoding="utf-8"))
    return {
        "status": "ready" if package.get("quality", {}).get("accepted_for_replay") else "quality_blocked",
        "accepted_for_replay": bool(package.get("quality", {}).get("accepted_for_replay")),
        "package": package,
    }


def load_population_exposure() -> dict[str, Any]:
    if not PARADISE_POPULATION.exists():
        return {
            "status": "not_built",
            "path": str(PARADISE_POPULATION.relative_to(ROOT)),
            "reason": "Run scripts/build_paradise_population.py with CENSUS_API_KEY configured.",
            "accepted_for_area_exposure": False,
        }
    package = json.loads(PARADISE_POPULATION.read_text(encoding="utf-8"))
    accepted = bool(
        package.get("metadata", {}).get("quality", {}).get("accepted_for_area_exposure")
    )
    return {
        "status": "ready" if accepted else "quality_blocked",
        "accepted_for_area_exposure": accepted,
        "package": package,
    }
