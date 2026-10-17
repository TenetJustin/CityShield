from __future__ import annotations

import os


def source_registry(city_selected: bool = False) -> list[dict]:
    return [
        {
            "source_id": "nasa-firms",
            "role": "active fire detections and FRP",
            "adapter": "implemented",
            "credentials": "configured" if os.getenv("FIRMS_MAP_KEY") else "missing FIRMS_MAP_KEY",
            "city_dependency": "bounding box and cell mapper",
            "ready": city_selected and bool(os.getenv("FIRMS_MAP_KEY")),
        },
        {
            "source_id": "noaa-nws",
            "role": "hourly weather forecast",
            "adapter": "implemented",
            "credentials": "not required",
            "city_dependency": "city centroid or weather sampling points",
            "ready": city_selected,
        },
        {
            "source_id": "nifc-wfigs",
            "role": "incident locations and incident metadata",
            "adapter": "implemented",
            "credentials": "not required",
            "city_dependency": "bounding box and feature-to-event mapping",
            "ready": city_selected,
        },
        {
            "source_id": "landfire",
            "role": "fuel and vegetation layers",
            "adapter": "file contract ready; download selection deferred",
            "credentials": "product-dependent",
            "city_dependency": "area of interest and raster aggregation",
            "ready": False,
        },
        {
            "source_id": "usgs-3dep",
            "role": "terrain, slope and aspect",
            "adapter": "file contract ready; download selection deferred",
            "credentials": "not required",
            "city_dependency": "area of interest and raster aggregation",
            "ready": False,
        },
        {
            "source_id": "local-response-data",
            "role": "roads, closures, evacuation zones and resources",
            "adapter": "canonical upload contract ready",
            "credentials": "city-dependent",
            "city_dependency": "authoritative local endpoints or files",
            "ready": False,
        },
    ]


def delivery_readiness(city_selected: bool = False) -> dict:
    """Delivery gates separate demo reliability from operational readiness."""

    firms_key = bool(os.getenv("FIRMS_MAP_KEY"))
    datasets = [
        {
            "dataset": "Active fire detections",
            "source": "NASA FIRMS",
            "adapter_ready": True,
            "city_input_needed": True,
            "live_ready": city_selected and firms_key,
            "fallback": "versioned incident snapshot",
            "minimum_acceptance": "timestamps, coordinates, confidence and source identity",
        },
        {
            "dataset": "Weather and forecast",
            "source": "NOAA / NWS",
            "adapter_ready": True,
            "city_input_needed": True,
            "live_ready": city_selected,
            "fallback": "cached issued forecast",
            "minimum_acceptance": "issue time, valid time, wind, humidity and temperature",
        },
        {
            "dataset": "Incident and perimeter",
            "source": "NIFC WFIGS + historical perimeter package",
            "adapter_ready": True,
            "city_input_needed": True,
            "live_ready": city_selected,
            "fallback": "versioned GeoJSON perimeter sequence",
            "minimum_acceptance": "geometry, incident ID, observed time and availability time",
        },
        {
            "dataset": "Terrain and fuels",
            "source": "USGS 3DEP + LANDFIRE",
            "adapter_ready": False,
            "city_input_needed": True,
            "live_ready": False,
            "fallback": "preprocessed city grid bundled at build time",
            "minimum_acceptance": "documented CRS, resolution, date and aggregation method",
        },
        {
            "dataset": "Population, roads and response resources",
            "source": "Census + authoritative local data",
            "adapter_ready": False,
            "city_input_needed": True,
            "live_ready": False,
            "fallback": "versioned scenario package; resources clearly marked illustrative",
            "minimum_acceptance": "license, vintage, geography and missing-value report",
        },
    ]
    return {
        "competition_demo_ready": True,
        "offline_replay_ready": True,
        "live_city_ready": all(item["live_ready"] for item in datasets),
        "city_selected": city_selected,
        "policy": "Live failure falls back to a labelled cached replay; synthetic data is never presented as live.",
        "datasets": datasets,
        "gates": [
            {
                "id": "demo",
                "label": "Competition demonstration",
                "status": "pass",
                "reason": "Deterministic replay, forecast, decision and audit paths run without network access.",
            },
            {
                "id": "historical",
                "label": "Historical validation",
                "status": "blocked" if not city_selected else "review",
                "reason": "Requires a selected city and one time-aligned independent incident.",
            },
            {
                "id": "live",
                "label": "Live operational feed",
                "status": "blocked" if not city_selected else "review",
                "reason": "Requires city mapping, source monitoring and freshness checks.",
            },
        ],
    }
