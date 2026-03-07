from __future__ import annotations

from dataclasses import fields
from typing import Any
import random
from dataclasses import dataclass, field, replace

import numpy as np

from app.schemas import PatientSeed, ScenarioDefinition, VitalPayload, utc_now_iso


METRICS = ("hr", "spo2", "sbp", "dbp", "rr", "temp")
DEFAULT_NORMAL_BASELINE = {
    "hr": 76.0,
    "spo2": 98.0,
    "sbp": 124.0,
    "dbp": 77.0,
    "rr": 16.0,
    "temp": 36.8,
}


@dataclass
class PatientSimulator:
    patient: PatientSeed
    scenario: ScenarioDefinition
    baseline: dict[str, float]
    noise: dict[str, float]
    clamp: dict[str, tuple[float, float]]
    tick_seconds: int
    current_values: dict[str, float] = field(init=False)
    phase_index: int = 0
    ticks_in_phase: int = 0
    battery: int = 100
    instant_jump_done: bool = False

    def __post_init__(self) -> None:
        self.current_values = dict(self.baseline)

    def _active_phase(self):
        if self.phase_index >= len(self.scenario.timeline):
            return self.scenario.timeline[-1]
        return self.scenario.timeline[self.phase_index]

    def _advance_phase_if_needed(self) -> None:
        phase = self._active_phase()
        phase_ticks = max(1, int((phase.duration_minutes * 60) / self.tick_seconds))
        if self.ticks_in_phase < phase_ticks:
            return
        if self.phase_index < len(self.scenario.timeline) - 1:
            self.phase_index += 1
            self.ticks_in_phase = 0
            self.instant_jump_done = False

    def _apply_phase(self) -> None:
        phase = self._active_phase()
        if self.scenario.stabilize_to_baseline:
            for metric, base_value in self.baseline.items():
                current = self.current_values[metric]
                diff = base_value - current
                self.current_values[metric] = current + (diff * self.scenario.stabilize_factor)

        if phase.instant_jump and not self.instant_jump_done:
            for metric, delta in phase.instant_jump.items():
                if metric in self.current_values:
                    self.current_values[metric] += delta
            self.instant_jump_done = True

        if phase.target_shift:
            adaptation_rate = phase.adaptation_rate if phase.adaptation_rate > 0 else 0.15
            for metric, shift in phase.target_shift.items():
                if metric in self.current_values:
                    target = self.baseline[metric] + shift
                    current = self.current_values[metric]
                    self.current_values[metric] = current + ((target - current) * adaptation_rate)

        if phase.trend_per_10min:
            ratio = self.tick_seconds / 600.0
            for metric, delta in phase.trend_per_10min.items():
                if metric in self.current_values:
                    self.current_values[metric] += delta * ratio

    def _apply_noise_and_clamp(self) -> dict[str, float]:
        values: dict[str, float] = {}
        clamp_source = self.clamp
        if self.scenario.clamp_override:
            clamp_source = {key: tuple(value) for key, value in self.scenario.clamp_override.items()}
        for metric in METRICS:
            sigma = self.noise.get(f"{metric}_sd", 0.0) * self.scenario.noise_multiplier
            if self.scenario.calculation_mode == "reference_stable_from_example":
                noise = float(np.random.normal(0, sigma))
                raw = self.current_values[metric] + noise
                low, high = clamp_source[metric]
                clamped = float(np.clip(raw, low, high))
            else:
                raw = self.current_values[metric] + random.gauss(0, sigma)
                low, high = clamp_source[metric]
                clamped = min(max(raw, low), high)
            values[metric] = round(clamped, 1) if metric == "temp" else round(clamped)

        min_pulse_pressure = 18
        if values["sbp"] - values["dbp"] < min_pulse_pressure:
            dbp_low = int(clamp_source["dbp"][0])
            values["dbp"] = max(dbp_low, int(values["sbp"] - min_pulse_pressure))
        return values

    def step(self) -> VitalPayload:
        self._apply_phase()
        noisy = self._apply_noise_and_clamp()
        self.battery = max(55, self.battery - random.choice([0, 0, 1]))
        self.ticks_in_phase += 1
        self._advance_phase_if_needed()

        map_value = int(round(noisy["dbp"] + ((noisy["sbp"] - noisy["dbp"]) / 3.0)))
        return VitalPayload(
            ts=utc_now_iso(),
            patient_id=self.patient.id,
            profile=self.patient.profile,
            scenario=self.patient.scenario,
            scenario_label=self.scenario.label,
            hr=int(noisy["hr"]),
            spo2=int(noisy["spo2"]),
            sbp=int(noisy["sbp"]),
            dbp=int(noisy["dbp"]),
            map=map_value,
            rr=int(noisy["rr"]),
            temp=float(noisy["temp"]),
            room=self.patient.room,
            battery=self.battery,
            postop_day=self.patient.postop_day,
            surgery_type=self.patient.surgery_type,
        )


def build_patient_simulators(
    config: dict,
    patients: list[PatientSeed],
    scenarios: dict[str, ScenarioDefinition],
    assignments: dict[str, dict[str, Any]] | None = None,
) -> list[PatientSimulator]:
    noise = config["noise"]
    clamp = {key: tuple(value) for key, value in config["clamp"].items()}
    tick_seconds = int(config.get("tick_seconds", 5))
    default_baseline = dict(config.get("default_normal_baseline", DEFAULT_NORMAL_BASELINE))
    simulators: list[PatientSimulator] = []
    patient_field_names = {item.name for item in fields(PatientSeed)}
    for patient in patients:
        assignment = assignments.get(patient.id, {}) if assignments else {}
        scenario_name = assignment.get("scenario", patient.scenario)
        replacement_payload = {
            field_name: assignment.get(field_name, getattr(patient, field_name))
            for field_name in patient_field_names
        }
        replacement_payload["scenario"] = scenario_name
        resolved_patient = replace(patient, **replacement_payload)
        scenario = scenarios[scenario_name]
        baseline = dict(default_baseline)
        if patient.baseline:
            baseline.update(patient.baseline)
        assignment_baseline = assignment.get("baseline")
        if isinstance(assignment_baseline, dict):
            baseline.update(assignment_baseline)
        if scenario.baseline_override:
            baseline.update(scenario.baseline_override)
        effective_noise = dict(noise)
        if scenario.noise_override:
            effective_noise.update(scenario.noise_override)
        simulators.append(
            PatientSimulator(
                patient=resolved_patient,
                scenario=scenario,
                baseline=baseline,
                noise=effective_noise,
                clamp=clamp,
                tick_seconds=tick_seconds,
            )
        )
    return simulators
