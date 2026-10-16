from __future__ import annotations

import hashlib
import json
from typing import Any

from .schemas import utc_now


class DecisionService:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.decisions: dict[str, dict[str, Any]] = {}

    def recommend(self, forecast: dict[str, Any]) -> dict[str, Any]:
        thresholds = self.config["decision_thresholds"]
        actions = []
        for item in forecast["cells"]:
            p50 = item["series"][-1]["p50"]
            p90 = item["series"][-1]["p90"]
            static = item["static"]
            exposure = static["population"] * (1 + static["critical_facilities"] * 0.5)
            score = p90 * exposure
            if p90 >= thresholds["evacuation_p90"]:
                action, priority = "prepare_evacuation", 5 if score >= 300 else 4
            elif p50 >= thresholds["resource_stage_p50"]:
                action, priority = "stage_resources", 3
            else:
                action, priority = "monitor", 1
            actions.append(
                {
                    "cell_id": item["cell_id"],
                    "action": action,
                    "priority": priority,
                    "score": round(score, 2),
                    "reason": f"120-min p90={p90:.2f}; exposed population={static['population']}",
                }
            )
        actions.sort(key=lambda item: (-item["priority"], -item["score"], item["cell_id"]))
        fingerprint = hashlib.sha256(
            json.dumps(actions, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        decision_id = f"decision-{len(self.decisions) + 1:04d}-{fingerprint}"
        decision = {
            "decision_run_id": decision_id,
            "forecast_run_id": forecast["forecast_run_id"],
            "created_at": utc_now().isoformat(),
            "execution_mode": "advisory_only",
            "status": "pending_human_review",
            "actions": actions,
            "safety_notes": [
                "No order or dispatch is executed automatically.",
                "Road capacity and live closures must be validated before operational use.",
            ],
        }
        self.decisions[decision_id] = decision
        return decision

    def review(self, decision_id: str, approved: bool, reviewer: str, note: str) -> dict[str, Any]:
        if decision_id not in self.decisions:
            raise KeyError(decision_id)
        decision = self.decisions[decision_id]
        if decision["status"] != "pending_human_review":
            raise ValueError("decision has already been reviewed")
        decision["status"] = "approved" if approved else "rejected"
        decision["review"] = {
            "reviewer": reviewer,
            "note": note,
            "reviewed_at": utc_now().isoformat(),
        }
        return decision

