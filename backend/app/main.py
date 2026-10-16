from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .audit import AuditLog
from .config import load_city_config
from .decision import DecisionService
from .demo import demo_observations
from .rsi import ControlledRSI
from .schemas import DecisionReview, Observation, RSIEvaluationRequest
from .world import WildfireWorldModel


config = load_city_config()
world = WildfireWorldModel(config)
decisions = DecisionService(config)
rsi = ControlledRSI()
audit = AuditLog()

app = FastAPI(
    title="CityShield",
    version="0.1.0",
    description="LinuxONE-ready real-time wildfire world-model research prototype",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "CityShield", "model_version": world.model_version}


@app.get("/api/v1/city")
def city():
    return config


@app.get("/api/v1/state")
def state():
    return world.snapshot()


@app.post("/api/v1/observations")
def ingest_observation(observation: Observation):
    try:
        world.ingest(observation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = audit.append(
        "observation_ingested", observation.model_dump(mode="json")
    )
    return {"accepted": True, "state": world.snapshot(), "audit_hash": record["hash"]}


@app.get("/api/v1/predict")
def predict():
    forecast = world.forecast()
    audit.append("forecast_created", {"forecast_run_id": forecast["forecast_run_id"]})
    return forecast


@app.post("/api/v1/decisions/recommend")
def recommend_decision():
    forecast = world.last_forecast or world.forecast()
    decision = decisions.recommend(forecast)
    audit.append("decision_recommended", decision)
    return decision


@app.post("/api/v1/decisions/{decision_id}/review")
def review_decision(decision_id: str, review: DecisionReview):
    try:
        decision = decisions.review(decision_id, review.approved, review.reviewer, review.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="decision not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.append("decision_reviewed", decision)
    return decision


@app.post("/api/v1/rsi/evaluate")
def evaluate_rsi(request: RSIEvaluationRequest):
    if world.last_forecast is None:
        raise HTTPException(status_code=409, detail="create a forecast before RSI evaluation")
    unknown = set(request.burned_cells) - set(world.cells)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown cells: {sorted(unknown)}")
    candidate = rsi.evaluate(request.event_id, request.burned_cells, world.last_forecast)
    audit.append("rsi_shadow_candidate_created", candidate)
    return candidate


@app.post("/api/v1/rsi/candidates/{candidate_id}/approve")
def approve_rsi_candidate(candidate_id: str, reviewer: str):
    try:
        candidate = rsi.approve(candidate_id, reviewer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="candidate not found") from exc
    audit.append("rsi_candidate_approved_for_next_version", candidate)
    return candidate


@app.get("/api/v1/audits")
def audits():
    return {"records": audit.list()}


@app.post("/api/v1/demo/reset")
def reset_demo():
    world.reset()
    decisions.decisions.clear()
    rsi.candidates.clear()
    audit.clear()
    return {"reset": True}


@app.post("/api/v1/demo/replay")
def replay_demo():
    for observation in demo_observations():
        world.ingest(observation)
        audit.append("demo_observation_ingested", observation.model_dump(mode="json"))
    forecast = world.forecast()
    decision = decisions.recommend(forecast)
    audit.append("demo_forecast_created", {"forecast_run_id": forecast["forecast_run_id"]})
    audit.append("demo_decision_recommended", decision)
    return {"observations": len(demo_observations()), "forecast": forecast, "decision": decision}

