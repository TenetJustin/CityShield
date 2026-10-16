#!/usr/bin/env python3
"""Exercise the full local demo through HTTP without external dependencies."""

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen


BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def request(path: str, method: str = "GET", payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(
        BASE + path,
        method=method,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=10) as response:
        return json.load(response)


request("/api/v1/demo/reset", "POST")
demo = request("/api/v1/demo/replay", "POST")
assert demo["forecast"]["cells"]
assert demo["decision"]["status"] == "pending_human_review"
scenario = request(
    "/api/v1/scenarios/simulate",
    "POST",
    {"name": "dry_gust", "wind_speed_multiplier": 1.7, "humidity_delta_pct": -10},
)
assert scenario["simulation_run_id"]
audit = request("/api/v1/audits")
assert audit["verification"]["valid"] is True
print("CityShield smoke test passed")

