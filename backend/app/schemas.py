from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    kind: Literal[
        "hotspot",
        "perimeter",
        "wind_speed",
        "wind_direction",
        "humidity",
        "temperature",
        "road_closure",
        "resource_status",
    ]
    cell_id: str | None = None
    value: float
    unit: str = Field(min_length=1)
    valid_at: datetime
    available_at: datetime
    forecast_issued_at: datetime | None = None
    source: str = Field(min_length=1)
    provider_record_id: str | None = None
    source_crs: str | None = None
    native_resolution_m: float | None = Field(default=None, gt=0)
    quality_flag: Literal["observed", "derived", "forecast", "synthetic-demo"]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("valid_at", "available_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_temporal_visibility(self):
        if self.quality_flag != "forecast" and self.available_at < self.valid_at:
            raise ValueError("non-forecast available_at cannot precede valid_at")
        if self.quality_flag == "forecast":
            if self.forecast_issued_at is None:
                raise ValueError("forecast records require forecast_issued_at")
            if self.forecast_issued_at > self.available_at:
                raise ValueError("forecast_issued_at cannot follow available_at")
        return self

    def dedupe_key(self) -> str:
        identity = self.provider_record_id or (
            f"{self.event_id}|{self.kind}|{self.cell_id}|{self.valid_at.isoformat()}|{self.value}"
        )
        return f"{self.source}|{identity}"


class DecisionAction(BaseModel):
    cell_id: str
    action: Literal[
        "prepare_evacuation",
        "stage_resources",
        "request_mutual_aid_review",
        "monitor",
    ]
    priority: int = Field(ge=1, le=5)
    reason: str


class DecisionReview(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=1)
    note: str = ""


class DecisionOutcome(BaseModel):
    outcome: Literal["executed", "partially_executed", "not_executed", "superseded"]
    reviewer: str = Field(min_length=1)
    note: str = ""


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: str = Field(default="custom", min_length=1, max_length=80)
    wind_speed_multiplier: float = Field(default=1.0, ge=0.0, le=3.0)
    wind_direction_delta_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    humidity_delta_pct: float = Field(default=0.0, ge=-50.0, le=50.0)
    suppression_effectiveness: float = Field(default=0.0, ge=0.0, le=0.9)
    unavailable_resource_cells: list[str] = Field(default_factory=list)


class RSIGateRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    held_out_replay_passed: bool
    safety_review_passed: bool
    note: str = ""


class RSIEvaluationRequest(BaseModel):
    event_id: str = Field(min_length=1)
    burned_cells: list[str]


class EvacuationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_at_utc: str = Field(min_length=10)
    seed: int = Field(default=20181108, ge=0, le=2_147_483_647)
    shelter_capacity_factor: float = Field(default=1.0, gt=0.0, le=3.0)
    include_fire_hazard: bool = True


class EvacuationCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_times: list[str] | None = None
    seed: int = Field(default=20181108, ge=0, le=2_147_483_647)
    shelter_capacity_factor: float = Field(default=1.0, gt=0.0, le=3.0)
    include_fire_hazard: bool = True


class ResourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at_utc: str = Field(min_length=10)
    lead_minutes: int = Field(default=120, ge=10, le=720)
    strategy: Literal["exposure_weighted", "nearest_first", "none"] = "exposure_weighted"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

