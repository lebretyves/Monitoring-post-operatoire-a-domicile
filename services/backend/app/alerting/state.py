from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any


OPS = {
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "==": lambda left, right: left == right,
}


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class AlertState:
    def __init__(self, max_samples: int = 1024) -> None:
        self.metric_history: dict[str, dict[str, deque[tuple[datetime, float]]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=max_samples))
        )
        self.latest_snapshots: dict[str, dict[str, Any]] = {}
        self.last_alerts: dict[tuple[str, str], datetime] = {}
        self.active_rules: dict[tuple[str, str], bool] = {}

    def push(self, reading: dict[str, Any]) -> None:
        patient_id = reading["patient_id"]
        timestamp = parse_ts(reading["ts"])
        self.latest_snapshots[patient_id] = reading
        for metric in ("hr", "spo2", "sbp", "dbp", "map", "rr", "temp", "shock_index"):
            self.metric_history[patient_id][metric].append((timestamp, float(reading[metric])))

    def latest_value(self, patient_id: str, metric: str) -> float | None:
        values = self.metric_history[patient_id][metric]
        return values[-1][1] if values else None

    def latest_snapshot(self, patient_id: str) -> dict[str, Any] | None:
        return self.latest_snapshots.get(patient_id)

    def window(self, patient_id: str, metric: str, seconds: int) -> list[tuple[datetime, float]]:
        values = self.metric_history[patient_id][metric]
        if not values:
            return []
        now = values[-1][0]
        cutoff = now - timedelta(seconds=seconds)
        return [(ts, value) for ts, value in values if ts >= cutoff]

    def duration_satisfied(self, patient_id: str, metric: str, op: str, value: float, seconds: int) -> bool:
        samples = self.window(patient_id, metric, seconds)
        if not samples:
            return False
        earliest = samples[0][0]
        latest = samples[-1][0]
        if (latest - earliest).total_seconds() < max(0, seconds - 5):
            return False
        return all(OPS[op](sample_value, value) for _, sample_value in samples)

    def trend_delta(self, patient_id: str, metric: str, window_minutes: int) -> float | None:
        samples = self.window(patient_id, metric, window_minutes * 60)
        if len(samples) < 2:
            return None
        return samples[-1][1] - samples[0][1]

    def set_rule_active(self, patient_id: str, rule_id: str, is_active: bool) -> None:
        key = (patient_id, rule_id)
        if is_active:
            self.active_rules[key] = True
        else:
            self.active_rules.pop(key, None)

    def should_emit(self, patient_id: str, rule_id: str, cooldown_seconds: int) -> bool:
        key = (patient_id, rule_id)
        if self.active_rules.get(key):
            return False
        now = parse_ts(self.latest_snapshots[patient_id]["ts"])
        last = self.last_alerts.get(key)
        if last and (now - last).total_seconds() < cooldown_seconds:
            return False
        self.last_alerts[key] = now
        self.active_rules[key] = True
        return True

    def clear_patient(self, patient_id: str) -> None:
        self.metric_history.pop(patient_id, None)
        self.latest_snapshots.pop(patient_id, None)
        for key in [key for key in self.last_alerts if key[0] == patient_id]:
            self.last_alerts.pop(key, None)
        for key in [key for key in self.active_rules if key[0] == patient_id]:
            self.active_rules.pop(key, None)
