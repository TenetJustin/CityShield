from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .adapters import source_registry
from .audit import AuditLog
from .config import load_city_config, readiness
from .decision import DecisionService
from .demo import demo_observations
from .rsi import ControlledRSI
from .schemas import (
    DecisionOutcome,
    DecisionReview,
    Observation,
    RSIEvaluationRequest,
    RSIGateRequest,
    ScenarioRequest,
)
from .world import WildfireWorldModel


config = load_city_config()
world = WildfireWorldModel(config)
decisions = DecisionService(config)
rsi = ControlledRSI()
audit_path = Path(
    os.getenv(
        "CITYSHIELD_AUDIT_PATH",
        str(Path(__file__).resolve().parents[1] / "data" / "runtime" / "audit.jsonl"),
    )
)
audit = AuditLog(audit_path)
started_at = time.time()
metrics = {
    "observations_ingested": 0,
    "duplicates_rejected": 0,
    "forecasts_created": 0,
    "scenarios_created": 0,
    "decisions_created": 0,
    "rsi_candidates_created": 0,
    "last_forecast_latency_ms": None,
}

app = FastAPI(
    title="CityShield",
    version="0.2.0",
    description="LinuxONE-ready real-time wildfire world-model research prototype",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CITYSHIELD_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    .split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _audit(event_type: str, payload: dict) -> dict:
    return audit.append(event_type, payload)


def _create_forecast(scenario: ScenarioRequest | None = None) -> dict:
    start = time.perf_counter()
    try:
        forecast = world.forecast(scenario=scenario)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    if scenario is None or scenario.name == "baseline":
        metrics["forecasts_created"] += 1
        metrics["last_forecast_latency_ms"] = elapsed_ms
    else:
        metrics["scenarios_created"] += 1
    _audit(
        "forecast_created" if scenario is None else "scenario_created",
        {
            "forecast_run_id": forecast["forecast_run_id"],
            "scenario": forecast["scenario"],
            "latency_ms": elapsed_ms,
        },
    )
    forecast["latency_ms"] = elapsed_ms
    return forecast


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "CityShield",
        "version": app.version,
        "model_version": world.model_version,
        "uptime_seconds": round(time.time() - started_at, 2),
        "deployment_target": "IBM LinuxONE / OCI-compatible Linux",
    }


@app.get("/api/v1/readiness")
def system_readiness():
    result = readiness(config)
    result["sources"] = source_registry(result["checks"]["city_selected"])
    result["audit"] = audit.verify()
    result["non_city_platform_complete"] = True
    return result


@app.get("/api/v1/metrics")
def system_metrics():
    return {**metrics, "uptime_seconds": round(time.time() - started_at, 2)}


@app.get("/api/v1/city")
def city():
    return config


@app.get("/api/v1/sources")
def sources():
    return {
        "sources": source_registry(config.get("city_id") != "TBD_US_CITY"),
        "policy": "Unavailable sources fail visibly; synthetic data is never labeled live.",
    }


@app.get("/api/v1/state")
def state():
    return world.snapshot()


@app.post("/api/v1/observations")
def ingest_observation(observation: Observation):
    try:
        accepted = world.ingest(observation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if accepted:
        metrics["observations_ingested"] += 1
        record = _audit("observation_ingested", observation.model_dump(mode="json"))
    else:
        metrics["duplicates_rejected"] += 1
        record = _audit("duplicate_observation_rejected", {"dedupe_key": observation.dedupe_key()})
    return {
        "accepted": accepted,
        "duplicate": not accepted,
        "state": world.snapshot(),
        "audit_hash": record["hash"],
    }


@app.get("/api/v1/predict")
def predict():
    return _create_forecast()


@app.get("/api/v1/scenarios/presets")
def scenario_presets():
    return {
        "presets": [
            ScenarioRequest(name="baseline").model_dump(mode="json"),
            ScenarioRequest(
                name="wind_shift",
                wind_speed_multiplier=1.4,
                wind_direction_delta_deg=90,
            ).model_dump(mode="json"),
            ScenarioRequest(
                name="dry_gust",
                wind_speed_multiplier=1.7,
                humidity_delta_pct=-10,
            ).model_dump(mode="json"),
            ScenarioRequest(
                name="suppression_support",
                suppression_effectiveness=0.35,
            ).model_dump(mode="json"),
        ]
    }


@app.post("/api/v1/scenarios/simulate")
def simulate_scenario(scenario: ScenarioRequest):
    unknown = set(scenario.unavailable_resource_cells) - set(world.cells)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown cells: {sorted(unknown)}")
    baseline = world.last_forecast or _create_forecast()
    scenario_result = _create_forecast(scenario)
    delta = []
    baseline_by_cell = {item["cell_id"]: item for item in baseline["cells"]}
    for item in scenario_result["cells"]:
        baseline_item = baseline_by_cell[item["cell_id"]]
        delta.append(
            {
                "cell_id": item["cell_id"],
                "delta_p90": round(
                    item["series"][-1]["p90"] - baseline_item["series"][-1]["p90"], 4
                ),
            }
        )
    simulation_id = hashlib.sha256(
        f"{baseline['forecast_run_id']}|{scenario_result['forecast_run_id']}".encode()
    ).hexdigest()[:16]
    return {
        "simulation_run_id": simulation_id,
        "baseline": baseline,
        "scenario": scenario_result,
        "delta": delta,
    }


@app.post("/api/v1/decisions/recommend")
def recommend_decision(forecast_run_id: str | None = None):
    forecast = world.last_forecast or _create_forecast()
    if forecast_run_id and forecast_run_id != forecast["forecast_run_id"]:
        raise HTTPException(status_code=409, detail="forecast_run_id is not the current frozen baseline")
    before = len(decisions.decisions)
    decision = decisions.recommend(forecast, world.operational)
    if len(decisions.decisions) > before:
        metrics["decisions_created"] += 1
        _audit("decision_recommended", decision)
    return decision


@app.get("/api/v1/decisions")
def list_decisions():
    return {"decisions": decisions.list()}


@app.post("/api/v1/decisions/{decision_id}/review")
def review_decision(decision_id: str, review: DecisionReview):
    try:
        decision = decisions.review(decision_id, review.approved, review.reviewer, review.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="decision not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit("decision_reviewed", decision)
    return decision


@app.post("/api/v1/decisions/{decision_id}/outcome")
def decision_outcome(decision_id: str, outcome: DecisionOutcome):
    try:
        decision = decisions.record_outcome(
            decision_id, outcome.outcome, outcome.reviewer, outcome.note
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="decision not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit("decision_outcome_recorded", decision)
    return decision


@app.post("/api/v1/rsi/evaluate")
def evaluate_rsi(request: RSIEvaluationRequest):
    if world.last_forecast is None:
        raise HTTPException(status_code=409, detail="create a baseline forecast before RSI evaluation")
    unknown = set(request.burned_cells) - set(world.cells)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown cells: {sorted(unknown)}")
    candidate = rsi.evaluate(request.event_id, request.burned_cells, world.last_forecast)
    metrics["rsi_candidates_created"] += 1
    _audit("rsi_shadow_candidate_created", candidate)
    return candidate


@app.get("/api/v1/rsi/candidates")
def list_rsi_candidates():
    return {"candidates": rsi.list(), "active_model_version": world.model_version}


@app.post("/api/v1/rsi/candidates/{candidate_id}/gate")
def gate_rsi_candidate(candidate_id: str, gate: RSIGateRequest):
    try:
        candidate = rsi.approve(
            candidate_id,
            gate.reviewer,
            gate.held_out_replay_passed,
            gate.safety_review_passed,
            gate.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="candidate not found") from exc
    _audit("rsi_candidate_gate_reviewed", candidate)
    return candidate


@app.get("/api/v1/audits")
def audits(limit: int = Query(default=100, ge=1, le=500)):
    records = audit.list()
    return {"records": records[-limit:], "verification": audit.verify()}


@app.post("/api/v1/demo/reset")
def reset_demo():
    world.reset()
    decisions.decisions.clear()
    rsi.candidates.clear()
    audit.clear()
    for key in metrics:
        metrics[key] = None if key == "last_forecast_latency_ms" else 0
    return {"reset": True}


@app.post("/api/v1/demo/replay")
def replay_demo():
    accepted = 0
    for observation in demo_observations():
        if world.ingest(observation):
            accepted += 1
            metrics["observations_ingested"] += 1
            _audit("demo_observation_ingested", observation.model_dump(mode="json"))
    forecast = _create_forecast()
    decision = decisions.recommend(forecast, world.operational)
    metrics["decisions_created"] += 1
    _audit("demo_decision_recommended", decision)
    return {"observations": accepted, "forecast": forecast, "decision": decision}


@app.get("/api/v1/demo/stream")
async def stream_demo(delay_ms: int = Query(default=250, ge=0, le=5000)):
    async def event_stream():
        for observation in demo_observations():
            accepted = world.ingest(observation)
            if accepted:
                metrics["observations_ingested"] += 1
                _audit("stream_observation_ingested", observation.model_dump(mode="json"))
            event = {
                "type": "observation",
                "accepted": accepted,
                "observation": observation.model_dump(mode="json"),
                "state": world.snapshot(),
            }
            yield f"event: observation\ndata: {json.dumps(event, default=str)}\n\n"
            await asyncio.sleep(delay_ms / 1000)
        forecast = _create_forecast()
        decision = decisions.recommend(forecast, world.operational)
        metrics["decisions_created"] += 1
        _audit("stream_decision_recommended", decision)
        yield f"event: complete\ndata: {json.dumps({'forecast': forecast, 'decision': decision})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
