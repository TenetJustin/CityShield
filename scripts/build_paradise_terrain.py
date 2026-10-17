"""Sample USGS 3DEP EPQS elevations for a display-only Paradise terrain mesh."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://epqs.nationalmap.gov/v1/json"
SIZE = 7


async def main() -> None:
    geography = json.loads((ROOT / "data/paradise/geography_2025.geojson").read_text())
    west, south, east, north = geography["bbox"]
    semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(timeout=35) as client:
        async def point(row: int, col: int) -> dict:
            lon = west + (east - west) * col / (SIZE - 1)
            lat = north - (north - south) * row / (SIZE - 1)
            async with semaphore:
                for attempt in range(3):
                    try:
                        response = await client.get(SOURCE, params={
                            "x": lon, "y": lat, "wkid": 4326,
                            "units": "Meters", "includeDate": "true",
                        })
                        response.raise_for_status()
                        data = response.json()
                        elevation = float(data["value"])
                        if elevation < -500 or elevation > 5000:
                            raise ValueError("out-of-range elevation")
                        return {
                            "row": row, "col": col, "longitude": round(lon, 7),
                            "latitude": round(lat, 7), "elevation_m": round(elevation, 2),
                            "resolution_m": data.get("resolution"),
                            "acquisition_date": data.get("attributes", {}).get("AcquisitionDate"),
                        }
                    except (httpx.HTTPError, KeyError, ValueError):
                        if attempt == 2:
                            raise
                        await asyncio.sleep(1 + attempt)
            raise AssertionError("unreachable")

        samples = await asyncio.gather(*(point(row, col) for row in range(SIZE) for col in range(SIZE)))
    output = {
        "name": "Paradise 3DEP elevation samples",
        "purpose": "display-only terrain interpolation, not a fire-spread DEM",
        "source": SOURCE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grid_size": SIZE,
        "bbox": geography["bbox"],
        "vertical_unit": "meters",
        "samples": samples,
    }
    target = ROOT / "data/paradise/terrain_3dep_7x7.json"
    target.write_text(json.dumps(output, separators=(",", ":")))
    print(f"Wrote {target}: {len(samples)} samples")


if __name__ == "__main__":
    asyncio.run(main())
