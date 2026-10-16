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
