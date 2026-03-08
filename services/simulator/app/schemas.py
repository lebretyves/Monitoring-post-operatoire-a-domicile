from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class PatientSeed:
    id: str
    full_name: str
    profile: str
    risk_level: str
    room: str
    age: int
    surgery_type: str
    postop_day: int
    scenario: str
    history: list[str]
    notes: str
    baseline: dict[str, float] | None = None


@dataclass
class Phase:
    phase: str
    duration_minutes: float
    trend_per_10min: dict[str, float]
    instant_jump: dict[str, float]
    target_shift: dict[str, float] | None = None
    adaptation_rate: float = 0.0


@dataclass
class ScenarioDefinition:
    name: str
    label: str
    timeline: list[Phase]
    calculation_mode: str = "default"
    repeat_timeline: bool = False
    noise_multiplier: float = 1.0
    stabilize_to_baseline: bool = False
    stabilize_factor: float = 0.0
    baseline_override: dict[str, float] | None = None
    noise_override: dict[str, float] | None = None
    clamp_override: dict[str, list[float]] | None = None
    initial_shift_by_postop_day: dict[str, dict[str, float]] | None = None
    onset_delay_range_minutes: list[float] | None = None


@dataclass
class VitalPayload:
    ts: str
    patient_id: str
    profile: str
    scenario: str
    scenario_label: str
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
    is_historical: bool = False
    backfill_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "patient_id": self.patient_id,
            "profile": self.profile,
            "scenario": self.scenario,
            "scenario_label": self.scenario_label,
            "hr": self.hr,
            "spo2": self.spo2,
            "sbp": self.sbp,
            "dbp": self.dbp,
            "map": int(round(self.map)),
            "rr": self.rr,
            "temp": round(self.temp, 1),
            "room": self.room,
            "battery": self.battery,
            "postop_day": self.postop_day,
            "surgery_type": self.surgery_type,
            "is_historical": self.is_historical,
            "backfill_only": self.backfill_only,
        }
