"""Build a frozen 2018 Camp Fire FIRMS package for Paradise.

The NASA FIRMS MAP_KEY is read only from the environment and is never written
to the output package, logs or source manifest.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.adapters.base import BoundingBox
from backend.app.adapters.firms import FIRMSAdapter
from backend.app.history import PARADISE_FIRMS_HISTORY, build_firms_history_package


BOUNDS = BoundingBox(-121.70, 39.68, -121.52, 39.85)
PRODUCTS = ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP")
START_DATE = "2018-11-08"
DAYS = 2


async def fetch_history(map_key: str) -> tuple[list[dict], list[dict]]:
    requests = []
    records = []
    for product in PRODUCTS:
        adapter = FIRMSAdapter(map_key, product=product)
        product_records = await adapter.fetch(BOUNDS, days=DAYS, start_date=START_DATE)
        for record in product_records:
            records.append({**record, "product": product})
        requests.append(
            {
                "product": product,
                "start_date": START_DATE,
                "days": DAYS,
                "record_count": len(product_records),
            }
        )
    return records, requests


def main() -> None:
    map_key = os.getenv("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        raise SystemExit("FIRMS_MAP_KEY is required; do not paste it into source code")
    records, source_requests = asyncio.run(fetch_history(map_key))
    package = build_firms_history_package(
        records,
        source_requests=source_requests,
        bounds={
            "west": BOUNDS.west,
            "south": BOUNDS.south,
            "east": BOUNDS.east,
            "north": BOUNDS.north,
        },
    )
    if not package["detections"]:
        raise SystemExit("NASA FIRMS returned zero detections; no package was written")
    target = Path(PARADISE_FIRMS_HISTORY)
    target.write_text(json.dumps(package, indent=2, sort_keys=True), encoding="utf-8")
    quality = package["quality"]
    print(
        f"Wrote {target} with {quality['record_count']} detections, "
        f"{quality['unique_acquisition_times']} acquisition times; "
        f"accepted_for_replay={quality['accepted_for_replay']}"
    )


if __name__ == "__main__":
    main()
