from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VitalReading(BaseModel):
    ts: str
    patient_id: str
    profile: str
    scenario: str
    hr: int
    spo2: int
    sbp: int
    dbp: int
    map: int
    rr: int
    temp: float
    room: str
    battery: int
    postop_day: int
    surgery_type: str
    shock_index: float = Field(default=0.0)


class PatientSummary(BaseModel):
    id: str
    full_name: str
    profile: str
    surgery_type: str
    postop_day: int
    risk_level: str
    room: str
    history: list[str]
    last_vitals: dict[str, Any] | None = None


class AlertRecord(BaseModel):
    id: int
    rule_id: str
    patient_id: str
    level: str
    status: str
    title: str
    message: str
    metric_snapshot: dict[str, Any]
    created_at: str
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None


class TrendPoint(BaseModel):
    ts: str
    values: dict[str, float]


class SummaryResponse(BaseModel):
    patient_id: str
    source: str
    summary: str
