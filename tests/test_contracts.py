from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.audit import AuditLog
from backend.app.schemas import Observation, ScenarioRequest


def test_forecast_may_be_available_before_valid_time():
    issued = datetime(2026, 1, 1, tzinfo=timezone.utc)
    item = Observation(
        event_id="forecast",
        kind="wind_speed",
        value=8.0,
        unit="m/s",
        valid_at=issued + timedelta(hours=3),
        available_at=issued + timedelta(minutes=2),
        forecast_issued_at=issued,
        source="test",
        quality_flag="forecast",
    )
    assert item.available_at < item.valid_at


def test_forecast_requires_issue_time():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="forecast_issued_at"):
        Observation(
            event_id="forecast",
            kind="wind_speed",
            value=8.0,
            unit="m/s",
            valid_at=now + timedelta(hours=3),
            available_at=now,
            source="test",
            quality_flag="forecast",
        )


def test_audit_chain_detects_tampering():
    audit = AuditLog()
    audit.append("one", {"value": 1})
    audit.append("two", {"value": 2})
    assert audit.verify()["valid"] is True
    audit._records[0]["payload"]["value"] = 99
    assert audit.verify()["valid"] is False


def test_audit_payload_is_frozen_from_later_mutation():
    audit = AuditLog()
    payload = {"status": "pending", "nested": {"value": 1}}
    audit.append("decision", payload)
    payload["status"] = "approved"
    payload["nested"]["value"] = 2
    assert audit.verify()["valid"] is True
    assert audit.list()[0]["payload"]["status"] == "pending"


def test_audit_reload_continues_existing_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = AuditLog(path)
    first.append("first", {"value": 1})
    second = AuditLog(path)
    second.append("second", {"value": 2})
    assert second.verify()["records"] == 2
    assert AuditLog(path).verify()["valid"] is True


def test_scenario_bounds_are_enforced():
    with pytest.raises(ValidationError):
        ScenarioRequest(wind_speed_multiplier=5)

