from datetime import datetime, timedelta, timezone

import pytest

from backend.app.config import load_city_config
from backend.app.decision import DecisionService
from backend.app.schemas import Observation
from backend.app.world import WildfireWorldModel


def observation(kind="hotspot", cell_id="B1", value=0.9):
    valid = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return Observation(
        event_id="test",
        kind=kind,
        cell_id=cell_id,
        value=value,
        valid_at=valid,
        available_at=valid + timedelta(minutes=1),
        source="test",
        quality_flag="synthetic-demo",
    )


def test_ingest_updates_state_and_forecast_is_reproducible():
    model = WildfireWorldModel(load_city_config())
    model.ingest(observation())
    assert model.snapshot()["cells"]["B1"]["burning_probability"] == 0.9
    first = model.forecast()
    second = model.forecast()
    assert first["forecast_run_id"] == second["forecast_run_id"]
    assert first["cells"] == second["cells"]


def test_available_time_cannot_precede_valid_time():
    model = WildfireWorldModel(load_city_config())
    item = observation()
    item.available_at = item.valid_at - timedelta(minutes=1)
    with pytest.raises(ValueError, match="available_at"):
        model.ingest(item)


def test_decision_is_advisory_and_requires_review():
    config = load_city_config()
    model = WildfireWorldModel(config)
    model.ingest(observation())
    decision = DecisionService(config).recommend(model.forecast())
    assert decision["execution_mode"] == "advisory_only"
    assert decision["status"] == "pending_human_review"

