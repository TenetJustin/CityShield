from __future__ import annotations

import csv
import io
from typing import Any

import httpx

from .base import AdapterError, BoundingBox


class FIRMSAdapter:
    """NASA FIRMS area CSV adapter.

    This adapter returns native detections. Mapping a detection to a CityShield
    cell is intentionally delegated to the selected city's spatial adapter.
    """

    source_id = "nasa-firms"
    endpoint = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

    def __init__(self, map_key: str, product: str = "VIIRS_SNPP_NRT") -> None:
        if not map_key:
            raise ValueError("FIRMS map key is required")
        self.map_key = map_key
        self.product = product

    async def fetch(self, bounds: BoundingBox, days: int = 1) -> list[dict[str, Any]]:
        if days not in range(1, 6):
            raise ValueError("FIRMS days must be 1..5")
        url = f"{self.endpoint}/{self.map_key}/{self.product}/{bounds.csv()}/{days}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise AdapterError(f"FIRMS request failed with HTTP {response.status_code}")
        return self.parse_csv(response.text)

    @staticmethod
    def parse_csv(content: str) -> list[dict[str, Any]]:
        rows = []
        for row in csv.DictReader(io.StringIO(content)):
            if not row.get("latitude") or not row.get("longitude"):
                continue
            rows.append(
                {
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "acq_date": row.get("acq_date"),
                    "acq_time": row.get("acq_time"),
                    "confidence": row.get("confidence"),
                    "frp": float(row["frp"]) if row.get("frp") else None,
                    "satellite": row.get("satellite"),
                    "instrument": row.get("instrument"),
                    "raw": row,
                }
            )
        return rows

