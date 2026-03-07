from __future__ import annotations

from pathlib import Path

from app.alerting.engine import AlertEngine
from app.alerting.rules_loader import load_rules
from app.alerting.state import AlertState


def _repo_root() -> Path:
    resolved = Path(__file__).resolve()
    for parent in resolved.parents:
        if (parent / "config").exists():
            return parent
    raise FileNotFoundError("config directory not found")


def test_composite_rule_triggers() -> None:
    root = _repo_root()
    rules = load_rules(root / "config" / "alert_rules.json")
    state = AlertState()
    engine = AlertEngine(ruleset=rules, state=state)
    samples = [
        ("2026-03-04T10:05:00Z", 102, 96),
        ("2026-03-04T10:10:00Z", 108, 94),
        ("2026-03-04T10:14:00Z", 116, 92),
        ("2026-03-04T10:15:00Z", 122, 89),
    ]
    alerts = []
    for ts, hr, spo2 in samples:
        reading = {
            "ts": ts,
            "patient_id": "PAT-004",
            "profile": "baseline_normale",
            "scenario": "pulmonary_embolism",
            "hr": hr,
            "spo2": spo2,
            "sbp": 110,
            "dbp": 70,
            "map": 83,
            "rr": 30,
            "temp": 37.1,
            "room": "A104",
            "battery": 95,
            "postop_day": 3,
            "surgery_type": "arthroplastie du genou",
            "shock_index": round(hr / 110, 2),
        }
        state.push(reading)
        alerts = engine.evaluate(reading)
    composite = next(alert for alert in alerts if alert["rule_id"] == "COMPOSITE_SPO2_DOWN_HR_UP")
    assert composite["metric_snapshot"]["false_positive_risk"] == "medium"
    assert composite["metric_snapshot"]["false_negative_risk"] == "high"
    assert composite["metric_snapshot"]["suspicion_stage"] == "degradation_confirmee"
    assert composite["metric_snapshot"]["remeasure_minutes"] == 0
