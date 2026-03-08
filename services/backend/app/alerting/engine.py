from __future__ import annotations

from typing import Any

from app.alerting.state import OPS, AlertState
from app.alerting.uncertainty import build_uncertainty_payload


class AlertEngine:
    def __init__(self, ruleset: dict[str, Any], state: AlertState) -> None:
        self.ruleset = ruleset
        self.state = state
        self.default_cooldown = int(ruleset.get("default_cooldown_seconds", 60))

    def evaluate(self, reading: dict[str, Any]) -> list[dict[str, Any]]:
        patient_id = reading["patient_id"]
        alerts: list[dict[str, Any]] = []
        for rule in self.ruleset.get("rules", []):
            matched = self._evaluate_logic(patient_id, rule["logic"])
            if matched:
                cooldown = int(rule.get("cooldown_seconds", self.default_cooldown))
                if not self.state.should_emit(patient_id, rule["id"], cooldown):
                    continue
                uncertainty = build_uncertainty_payload(self.ruleset, rule, reading)
                alerts.append(
                    {
                        "rule_id": rule["id"],
                        "patient_id": patient_id,
                        "level": rule["level"],
                        "status": "OPEN",
                        "title": rule["title"],
                        "message": rule["message"],
                        "metric_snapshot": {
                            key: reading[key]
                            for key in (
                                "ts",
                                "hr",
                                "spo2",
                                "sbp",
                                "dbp",
                                "map",
                                "rr",
                                "temp",
                                "shock_index",
                                "scenario",
                                "scenario_label",
                                "surgery_type",
                            )
                            if key in reading
                        }
                        | uncertainty,
                    }
                )
            else:
                self.state.set_rule_active(patient_id, rule["id"], False)
        return alerts

    def _evaluate_logic(self, patient_id: str, logic: dict[str, Any]) -> bool:
        if "all" in logic:
            return all(self._evaluate_condition(patient_id, condition) for condition in logic["all"])
        if "any" in logic:
            return any(self._evaluate_condition(patient_id, condition) for condition in logic["any"])
        return False

    def _evaluate_condition(self, patient_id: str, condition: dict[str, Any]) -> bool:
        if "all" in condition or "any" in condition:
            return self._evaluate_logic(patient_id, condition)
        metric = condition["metric"]
        if "trend" in condition:
            delta = self.state.trend_delta(patient_id, metric, int(condition["trend"]["window_minutes"]))
            if delta is None:
                return False
            target = float(condition["trend"]["delta"])
            return delta >= target if target >= 0 else delta <= target
        latest = self.state.latest_value(patient_id, metric)
        if latest is None:
            return False
        if "duration_seconds" in condition:
            return self.state.duration_satisfied(
                patient_id=patient_id,
                metric=metric,
                op=condition["op"],
                value=float(condition["value"]),
                seconds=int(condition["duration_seconds"]),
            )
        return OPS[condition["op"]](latest, float(condition["value"]))
