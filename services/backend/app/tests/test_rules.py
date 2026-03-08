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


def test_persistent_rule_emits_once_per_episode() -> None:
    root = _repo_root()
    rules = load_rules(root / "config" / "alert_rules.json")
    state = AlertState()
    engine = AlertEngine(ruleset=rules, state=state)
    emitted_rule_ids: list[str] = []
    for second in range(0, 91, 5):
        ts = f"2026-03-04T10:00:{second:02d}Z" if second < 60 else f"2026-03-04T10:01:{second - 60:02d}Z"
        reading = {
            "ts": ts,
            "patient_id": "PAT-002",
            "profile": "baseline_normale",
            "scenario": "pneumonia_ira",
            "hr": 118,
            "spo2": 88,
            "sbp": 112,
            "dbp": 72,
            "map": 85,
            "rr": 32,
            "temp": 38.4,
            "room": "A102",
            "battery": 98,
            "postop_day": 2,
            "surgery_type": "prothese de hanche",
            "shock_index": round(118 / 112, 2),
        }
        state.push(reading)
        emitted_rule_ids.extend(alert["rule_id"] for alert in engine.evaluate(reading))
    assert emitted_rule_ids.count("RESPIRATORY_CRITICAL") == 1


def test_temperature_rules_trigger_without_tachycardia() -> None:
    root = _repo_root()
    rules = load_rules(root / "config" / "alert_rules.json")
    state = AlertState()
    engine = AlertEngine(ruleset=rules, state=state)
    emitted_alerts: list[dict] = []
    for second in range(0, 121, 5):
        minute = second // 60
        second_in_minute = second % 60
        ts = f"2026-03-04T11:0{minute}:{second_in_minute:02d}Z"
        reading = {
            "ts": ts,
            "patient_id": "PAT-005",
            "profile": "baseline_normale",
            "scenario": "sepsis_progressive",
            "hr": 96,
            "spo2": 97,
            "sbp": 122,
            "dbp": 76,
            "map": 91,
            "rr": 18,
            "temp": 38.6,
            "room": "A105",
            "battery": 92,
            "postop_day": 2,
            "surgery_type": "chirurgie colorectale",
            "shock_index": round(96 / 122, 2),
        }
        state.push(reading)
        emitted_alerts.extend(engine.evaluate(reading))
    rule_ids = {alert["rule_id"] for alert in emitted_alerts}
    assert "TEMP_INFO" in rule_ids
    assert "TEMP_WARNING" in rule_ids
    assert "FEVER_WARNING" not in rule_ids
    temp_warning = next(alert for alert in emitted_alerts if alert["rule_id"] == "TEMP_WARNING")
    assert temp_warning["metric_snapshot"]["evidence_mode"] == "single_signal+persistence"
    assert temp_warning["metric_snapshot"]["suspicion_stage"] == "suspicion_a_confirmer"


def test_sbp_critical_triggers_without_map_or_shock_index_rule() -> None:
    root = _repo_root()
    rules = load_rules(root / "config" / "alert_rules.json")
    state = AlertState()
    engine = AlertEngine(ruleset=rules, state=state)
    emitted_alerts: list[dict] = []
    for second in range(0, 61, 5):
        ts = f"2026-03-04T12:00:{second:02d}Z" if second < 60 else "2026-03-04T12:01:00Z"
        reading = {
            "ts": ts,
            "patient_id": "PAT-003",
            "profile": "baseline_normale",
            "scenario": "hemorrhage_low_grade",
            "hr": 70,
            "spo2": 98,
            "sbp": 88,
            "dbp": 70,
            "map": 76,
            "rr": 16,
            "temp": 36.9,
            "room": "A103",
            "battery": 89,
            "postop_day": 1,
            "surgery_type": "colectomie",
            "shock_index": round(70 / 88, 2),
        }
        state.push(reading)
        emitted_alerts.extend(engine.evaluate(reading))
    rule_ids = {alert["rule_id"] for alert in emitted_alerts}
    assert "SBP_CRITICAL" in rule_ids
    assert "HEMODYNAMIC_WARNING" not in rule_ids
