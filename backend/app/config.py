from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "city.example.json"


@lru_cache(maxsize=1)
def load_city_config() -> dict[str, Any]:
    path = Path(os.getenv("CITYSHIELD_CONFIG", str(DEFAULT_CONFIG)))
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"city_id", "city_name", "model_grid_m", "cells"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"city configuration missing: {sorted(missing)}")
    cell_ids = [cell["id"] for cell in data["cells"]]
    if len(cell_ids) != len(set(cell_ids)):
        raise ValueError("cell ids must be unique")
    if sorted(data.get("forecast_horizons_minutes", [])) != data.get(
        "forecast_horizons_minutes", []
    ):
        raise ValueError("forecast horizons must be sorted")
    if any(int(value) <= 0 or int(value) % 30 for value in data["forecast_horizons_minutes"]):
        raise ValueError("forecast horizons must be positive 30-minute multiples")
    return data


def config_fingerprint(config: dict[str, Any]) -> str:
    import hashlib

    canonical = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def readiness(config: dict[str, Any]) -> dict[str, Any]:
    city_selected = config.get("city_id") not in {None, "", "TBD_US_CITY"}
    real_data = config.get("data_mode") == "real"
    checks = {
        "city_selected": city_selected,
        "real_data_mode": real_data,
        "grid_configured": bool(config.get("cells")),
        "advisory_only": bool(config.get("advisory_only", True)),
        "forecast_horizons_configured": bool(config.get("forecast_horizons_minutes")),
    }
    return {
        "status": "ready_for_real_data" if city_selected and real_data else "demo_ready",
        "checks": checks,
        "blocking_city_specific_items": [
            item
            for item, passed in {
                "select_city": city_selected,
                "replace_synthetic_grid": real_data,
            }.items()
            if not passed
        ],
    }

