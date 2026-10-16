from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    kind: Literal["hotspot", "perimeter", "wind_speed", "wind_direction", "humidity"]
    cell_id: str | None = None
    value: float
    valid_at: datetime
    available_at: datetime
    source: str = Field(min_length=1)
    quality_flag: Literal["observed", "derived", "forecast", "synthetic-demo"]

    @field_validator("valid_at", "available_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value


class DecisionAction(BaseModel):
    cell_id: str
    action: Literal["prepare_evacuation", "stage_resources", "monitor"]
    priority: int = Field(ge=1, le=5)
    reason: str


class DecisionReview(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=1)
    note: str = ""


class RSIEvaluationRequest(BaseModel):
    event_id: str = Field(min_length=1)
    burned_cells: list[str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

