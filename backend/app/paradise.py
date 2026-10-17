"""Paradise public-data view; deliberately separate from the exercise model."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .adapters.base import BoundingBox
from .adapters.firms import FIRMSAdapter
from .adapters.weather import NWSAdapter
from .adapters.wfigs import WFIGSAdapter


GEOGRAPHY = Path(__file__).resolve().parents[2] / "data" / "paradise" / "geography_2025.geojson"
HISTORICAL_FINAL = Path(__file__).resolve().parents[2] / "data" / "paradise" / "camp_fire_final_2018_town_clip.geojson"
TERRAIN = Path(__file__).resolve().parents[2] / "data" / "paradise" / "terrain_3dep_7x7.json"
LATITUDE, LONGITUDE = 39.7541919, -121.6064
BOUNDS = BoundingBox(-121.70, 39.68, -121.52, 39.85)
_cached: dict | None = None
_cached_until = 0.0
_lock = asyncio.Lock()


@lru_cache(maxsize=1)
def geography() -> dict:
    return json.loads(GEOGRAPHY.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def historical_final_perimeter() -> dict:
    return json.loads(HISTORICAL_FINAL.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def terrain_samples() -> dict:
    return json.loads(TERRAIN.read_text(encoding="utf-8"))


async def live_snapshot(force: bool = False) -> dict:
    """Refresh independent source observations every five minutes.

    A fetch failure is visible. A zero-result incident query means only that
    this source returned zero records in the query box, not that the area is safe.
    """
    global _cached, _cached_until
    if not force and _cached is not None and time.monotonic() < _cached_until:
        return _cached
    async with _lock:
        if not force and _cached is not None and time.monotonic() < _cached_until:
            return _cached
        firms_key = os.getenv("FIRMS_MAP_KEY", "")
        requests = [
            NWSAdapter().fetch_hourly(LATITUDE, LONGITUDE),
            WFIGSAdapter().fetch(BOUNDS),
        ]
        if firms_key:
            requests.append(FIRMSAdapter(firms_key).fetch(BOUNDS, days=1))
        outcomes = await asyncio.gather(*requests, return_exceptions=True)
        fetched_at = datetime.now(timezone.utc).isoformat()
        names = ["noaa-nws", "nifc-wfigs"] + (["nasa-firms"] if firms_key else [])
        sources = {}
        for name, outcome in zip(names, outcomes):
            if isinstance(outcome, BaseException):
                sources[name] = {"status": "unavailable", "fetched_at": fetched_at, "error": str(outcome)}
            else:
                sources[name] = {"status": "ok", "fetched_at": fetched_at, "count": len(outcome)}
        if not firms_key:
            sources["nasa-firms"] = {"status": "not_configured", "reason": "FIRMS_MAP_KEY is missing"}
        weather = outcomes[0] if not isinstance(outcomes[0], BaseException) else []
        incidents = outcomes[1] if not isinstance(outcomes[1], BaseException) else []
        hotspots = outcomes[2] if firms_key and not isinstance(outcomes[2], BaseException) else []
        _cached = {
            "area": "Paradise, California",
            "fetched_at": fetched_at,
            "cache_seconds": 300,
            "sources": sources,
            "hourly_forecast": weather[:12],
            "incidents": incidents,
            "satellite_detections": hotspots,
            "interpretation": "Public source observations only. A zero-result query does not establish safety; satellite detections are not a fire perimeter.",
            "operational_prediction_ready": False,
        }
        _cached_until = time.monotonic() + 300
        return _cached
