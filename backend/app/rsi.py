from __future__ import annotations

import hashlib
import json
from typing import Any

from .schemas import utc_now


class ControlledRSI:
    """Post-event improvement loop with shadow-only candidates and human promotion."""

    def __init__(self) -> None:
        self.candidates: dict[str, dict[str, Any]] = {}

    def evaluate(self, event_id: str, burned_cells: list[str], forecast: dict[str, Any]) -> dict[str, Any]:
        burned = set(burned_cells)
        probabilities = {
            item["cell_id"]: item["series"][-1]["p50"] for item in forecast["cells"]
        }
        brier = sum((prob - (1.0 if cell in burned else 0.0)) ** 2 for cell, prob in probabilities.items())
        brier /= max(1, len(probabilities))
        payload = {"event_id": event_id, "brier": round(brier, 5), "burned_cells": sorted(burned)}
        candidate_id = "candidate-" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        candidate = {
            "candidate_id": candidate_id,
            "created_at": utc_now().isoformat(),
            "status": "shadow",
            "evaluation": payload,
            "proposal": {
                "type": "review_spread_factor",
                "reason": "candidate generated from post-event scoring; requires replay validation",
            },
            "promotion_gate": [
                "backtest on held-out event",
                "no-regression safety check",
                "human approval",
                "version registration and rollback plan",
            ],
        }
        self.candidates[candidate_id] = candidate
        return candidate

    def approve(self, candidate_id: str, reviewer: str) -> dict[str, Any]:
        if candidate_id not in self.candidates:
            raise KeyError(candidate_id)
        candidate = self.candidates[candidate_id]
        candidate["status"] = "approved_for_next_version_only"
        candidate["approved_by"] = reviewer
        candidate["approved_at"] = utc_now().isoformat()
        candidate["active_model_changed"] = False
        return candidate

