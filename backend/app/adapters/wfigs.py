from __future__ import annotations

from typing import Any

import httpx

from .base import AdapterError, BoundingBox


class WFIGSAdapter:
    """Public WFIGS current incident feature service adapter."""

    source_id = "nifc-wfigs"
    endpoint = (
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
        "WFIGS_Incident_Locations_Current/FeatureServer/0/query"
    )

    async def fetch(self, bounds: BoundingBox) -> list[dict[str, Any]]:
        bounds.validate()
        params = {
            "where": "1=1",
            "geometry": bounds.csv(),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(self.endpoint, params=params)
        if response.status_code != 200:
            raise AdapterError(f"WFIGS request failed with HTTP {response.status_code}")
        payload = response.json()
        if "error" in payload:
            raise AdapterError(f"WFIGS returned an ArcGIS error: {payload['error'].get('message')}")
        return self.parse_geojson(payload)

    @staticmethod
    def parse_geojson(payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "properties": feature.get("properties", {}),
                "geometry": feature.get("geometry"),
            }
            for feature in payload.get("features", [])
            if feature.get("geometry")
        ]

