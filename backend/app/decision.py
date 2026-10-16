from __future__ import annotations

import hashlib
import json
from typing import Any

from .schemas import utc_now


class DecisionService:
    """Constrained advisory planner with explicit human and data gates."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.decisions: dict[str, dict[str, Any]] = {}

    def recommend(
        self,
        forecast: dict[str, Any],
        operational: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        operational = operational or {"road_closures": {}, "resource_status": {}}
        thresholds = self.config["decision_thresholds"]
        scenario = forecast.get("scenario", {})
        unavailable = set(scenario.get("unavailable_resource_cells", []))
        actions = []
        safety_adjustments = []
        for item in forecast["cells"]:
            p50 = item["series"][-1]["p50"]
            p90 = item["series"][-1]["p90"]
            static = item["static"]
            exposure = static["population"] * (
                1 + static["critical_facilities"] * thresholds["critical_facility_multiplier"]
            )
            score = p90 * exposure
            if p90 >= thresholds["evacuation_p90"]:
                action, priority = "prepare_evacuation", 5 if score >= 300 else 4
            elif p50 >= thresholds["resource_stage_p50"]:
                action, priority = "stage_resources", 3
            else:
                action, priority = "monitor", 1

            if item["cell_id"] in unavailable and action == "stage_resources":
                safety_adjustments.append(
                    {
                        "cell_id": item["cell_id"],
                        "requested": "stage_resources",
                        "applied": "request_mutual_aid_review",
                        "reason": "resource cell unavailable in scenario",
                    }
                )
                action = "request_mutual_aid_review"
                priority = max(priority, 4)

            if operational.get("road_closures", {}).get(item["cell_id"]):
                priority = min(5, priority + 1)
                route_note = "; road closure present—route must be revalidated"
            else:
                route_note = ""
            actions.append(
                {
                    "cell_id": item["cell_id"],
                    "action": action,
                    "priority": priority,
                    "score": round(score, 2),
                    "reason": (
                        f"{item['series'][-1]['horizon_minutes']}-min p90={p90:.2f}; "
                        f"exposed population={static['population']}{route_note}"
                    ),
                    "requires_human_approval": action != "monitor",
                }
            )
        actions.sort(key=lambda item: (-item["priority"], -item["score"], item["cell_id"]))
        fingerprint = hashlib.sha256(
            json.dumps(
                {"forecast_run_id": forecast["forecast_run_id"], "actions": actions},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12]
        existing = next(
            (
                decision
                for decision in self.decisions.values()
                if decision["decision_fingerprint"] == fingerprint
                and decision["status"] == "pending_human_review"
            ),
            None,
        )
        if existing:
            return existing
        decision_id = f"decision-{len(self.decisions) + 1:04d}-{fingerprint}"
        non_monitor = sum(item["action"] != "monitor" for item in actions)
        decision = {
            "decision_run_id": decision_id,
            "decision_fingerprint": fingerprint,
            "forecast_run_id": forecast["forecast_run_id"],
            "created_at": utc_now().isoformat(),
            "execution_mode": "advisory_only",
            "status": "pending_human_review",
            "summary": {
                "cells_requiring_action": non_monitor,
                "highest_priority": max(item["priority"] for item in actions),
            },
            "actions": actions,
            "safety_projection": {
                "adjustments": safety_adjustments,
                "automatic_execution": False,
                "route_optimization_enabled": False,
                "route_reason": "authoritative city road graph and live capacity are not configured",
            },
            "safety_notes": [
                "No warning, evacuation order, road closure or dispatch is executed automatically.",
                "Any route or capacity must be validated against authoritative local data.",
                "Synthetic or uncalibrated forecasts are demonstration evidence only.",
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
        decision["status"] = "approved_for_coordination" if approved else "rejected"
        decision["review"] = {
            "reviewer": reviewer,
            "note": note,
            "reviewed_at": utc_now().isoformat(),
        }
        return decision

    def record_outcome(
        self, decision_id: str, outcome: str, reviewer: str, note: str
    ) -> dict[str, Any]:
        if decision_id not in self.decisions:
            raise KeyError(decision_id)
        decision = self.decisions[decision_id]
        if decision["status"] == "pending_human_review":
            raise ValueError("decision must be reviewed before recording an outcome")
        decision["outcome"] = {
            "status": outcome,
            "reviewer": reviewer,
            "note": note,
            "recorded_at": utc_now().isoformat(),
        }
        decision["status"] = "closed"
        return decision

    def list(self) -> list[dict[str, Any]]:
        return sorted(self.decisions.values(), key=lambda item: item["created_at"], reverse=True)
