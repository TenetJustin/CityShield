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
    return data

