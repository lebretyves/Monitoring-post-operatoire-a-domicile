from __future__ import annotations

from pydantic import BaseModel, Field


class VitalPayload(BaseModel):
    ts: str
    patient_id: str
    profile: str
    scenario: str
    scenario_label: str | None = None
    hr: int
    spo2: int
    sbp: int
    dbp: int
    map: float | None = None
    rr: int
    temp: float
    room: str
    battery: int = Field(default=100)
    postop_day: int = Field(default=0)
    surgery_type: str = Field(default="")
    is_historical: bool = Field(default=False)
