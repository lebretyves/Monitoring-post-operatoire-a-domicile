from __future__ import annotations

import json
import os
from pathlib import Path

from app.schemas import PatientSeed, Phase, ScenarioDefinition


def _read_json(path: str | Path) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def get_simulation_path() -> Path:
    return Path(os.getenv("SIMULATION_CONFIG_PATH", "/app/config/simulation_scenarios.json"))


def get_patients_path() -> Path:
    return Path(os.getenv("PATIENTS_SEED_PATH", "/app/config/patients_seed.json"))


def load_simulation_config() -> dict:
    return _read_json(get_simulation_path())


def load_patients() -> list[PatientSeed]:
    payload = _read_json(get_patients_path())
    return [PatientSeed(**item) for item in payload]


def build_scenarios(config: dict) -> dict[str, ScenarioDefinition]:
    scenarios: dict[str, ScenarioDefinition] = {}
    for name, item in config["scenario_catalog"].items():
        timeline = [
            Phase(
                phase=phase["phase"],
                duration_minutes=phase["duration_minutes"],
                trend_per_10min=phase.get("trend_per_10min", {}),
                instant_jump=phase.get("instant_jump", {}),
                target_shift=phase.get("target_shift"),
                adaptation_rate=float(phase.get("adaptation_rate", 0.0)),
            )
            for phase in item["timeline"]
        ]
        scenarios[name] = ScenarioDefinition(name=name, label=item["label"], timeline=timeline)
        scenarios[name].calculation_mode = item.get("calculation_mode", "default")
        scenarios[name].repeat_timeline = bool(item.get("repeat_timeline", False))
        scenarios[name].noise_multiplier = float(item.get("noise_multiplier", 1.0))
        scenarios[name].stabilize_to_baseline = bool(item.get("stabilize_to_baseline", False))
        scenarios[name].stabilize_factor = float(item.get("stabilize_factor", 0.0))
        scenarios[name].baseline_override = item.get("baseline_override")
        scenarios[name].noise_override = item.get("noise_override")
        scenarios[name].clamp_override = item.get("clamp_override")
        scenarios[name].initial_shift_by_postop_day = item.get("initial_shift_by_postop_day")
        scenarios[name].onset_delay_range_minutes = item.get("onset_delay_range_minutes")
    return scenarios


def patient_scenario_map(config: dict) -> dict[str, str]:
    return {item["patient_id"]: item["scenario"] for item in config.get("patient_plan", [])}
