from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
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

    def request_url(
        self,
        bounds: BoundingBox,
        days: int = 1,
        start_date: date | str | None = None,
    ) -> str:
        if days not in range(1, 6):
            raise ValueError("FIRMS days must be 1..5")
        if isinstance(start_date, str):
            try:
                start_date = date.fromisoformat(start_date)
            except ValueError as exc:
                raise ValueError("FIRMS start_date must be YYYY-MM-DD") from exc
        url = f"{self.endpoint}/{self.map_key}/{self.product}/{bounds.csv()}/{days}"
        if start_date is not None:
            url += f"/{start_date.isoformat()}"
        return url

    async def fetch(
        self,
        bounds: BoundingBox,
        days: int = 1,
        start_date: date | str | None = None,
    ) -> list[dict[str, Any]]:
        url = self.request_url(bounds, days=days, start_date=start_date)
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
            record = {
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
            if record["acq_date"] and record["acq_time"]:
                acquired = datetime.strptime(
                    f"{record['acq_date']} {str(record['acq_time']).zfill(4)}",
                    "%Y-%m-%d %H%M",
                ).replace(tzinfo=timezone.utc)
                record["acquired_at"] = acquired.isoformat().replace("+00:00", "Z")
            else:
                record["acquired_at"] = None
            rows.append(record)
        return rows

