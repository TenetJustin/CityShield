from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .schemas import utc_now


class ControlledRSI:
    """Offline improvement loop with shadow candidates and hard promotion gates."""

    def __init__(self) -> None:
        self.candidates: dict[str, dict[str, Any]] = {}

    def evaluate(self, event_id: str, burned_cells: list[str], forecast: dict[str, Any]) -> dict[str, Any]:
        burned = set(burned_cells)
        probabilities = {
            item["cell_id"]: item["series"][-1]["p50"] for item in forecast["cells"]
        }
        labels = {cell: 1.0 if cell in burned else 0.0 for cell in probabilities}
        brier = sum((probabilities[cell] - labels[cell]) ** 2 for cell in probabilities)
        brier /= max(1, len(probabilities))
        epsilon = 1e-6
        log_loss = -sum(
            labels[cell] * math.log(max(epsilon, probabilities[cell]))
            + (1 - labels[cell]) * math.log(max(epsilon, 1 - probabilities[cell]))
            for cell in probabilities
        ) / max(1, len(probabilities))
        predicted = {cell for cell, probability in probabilities.items() if probability >= 0.5}
        true_positive = len(predicted & burned)
        false_positive = len(predicted - burned)
        false_negative = len(burned - predicted)
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        evaluation = {
            "event_id": event_id,
            "forecast_run_id": forecast["forecast_run_id"],
            "brier_score": round(brier, 5),
            "log_loss": round(log_loss, 5),
            "precision_at_0_5": round(precision, 5),
            "recall_at_0_5": round(recall, 5),
            "burned_cells": sorted(burned),
            "evaluated_cells": len(probabilities),
        }
        candidate_id = "candidate-" + hashlib.sha256(
            json.dumps(evaluation, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        candidate = {
            "candidate_id": candidate_id,
            "created_at": utc_now().isoformat(),
            "status": "shadow",
            "evaluation": evaluation,
            "proposal": {
                "type": "model_diagnostic_only",
                "recommended_investigation": self._diagnostic(precision, recall, brier),
                "automatic_parameter_change": False,
            },
            "gates": {
                "held_out_replay_passed": False,
                "safety_review_passed": False,
                "human_approval_recorded": False,
            },
            "promotion_policy": [
                "evaluate on a separate held-out incident",
                "show no safety regression on high-exposure cells",
                "record human approval",
                "register a new version and rollback target",
                "run in shadow before replacing the active version",
            ],
        }
        self.candidates[candidate_id] = candidate
        return candidate

    @staticmethod
    def _diagnostic(precision: float, recall: float, brier: float) -> str:
        if recall < 0.5:
            return "review under-spread bias, missed ignitions and observation latency"
        if precision < 0.5:
            return "review over-spread bias, fuel mapping and wind uncertainty"
        if brier > 0.25:
            return "review probability calibration before changing propagation dynamics"
        return "retain dynamics; collect another independent event before proposing a change"

    def approve(
        self,
        candidate_id: str,
        reviewer: str,
        held_out_replay_passed: bool,
        safety_review_passed: bool,
        note: str = "",
    ) -> dict[str, Any]:
        if candidate_id not in self.candidates:
            raise KeyError(candidate_id)
        candidate = self.candidates[candidate_id]
        candidate["gates"].update(
            {
                "held_out_replay_passed": held_out_replay_passed,
                "safety_review_passed": safety_review_passed,
                "human_approval_recorded": True,
            }
        )
        all_passed = held_out_replay_passed and safety_review_passed
        candidate["status"] = (
            "approved_for_versioned_shadow_release" if all_passed else "rejected_by_gate"
        )
        candidate["review"] = {
            "reviewer": reviewer,
            "note": note,
            "reviewed_at": utc_now().isoformat(),
        }
        candidate["active_model_changed"] = False
        return candidate

    def list(self) -> list[dict[str, Any]]:
        return sorted(self.candidates.values(), key=lambda item: item["created_at"], reverse=True)
