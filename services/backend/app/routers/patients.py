from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.ws.events import notifications_reset_event


router = APIRouter(prefix="/api/patients", tags=["patients"])

SURGERY_BAND_ORDER = ("strong", "medium", "weak")
POSTOP_DAY_ORDER = ("0", "1", "2", "3")
MINUTES_PER_DAY = 24 * 60


def _scenario_labels(simulation_config_path: Path) -> dict[str, str]:
    config = json.loads(simulation_config_path.read_text(encoding="utf-8"))
    return {
        name: item.get("label", name)
        for name, item in config.get("scenario_catalog", {}).items()
    }


def _pick_weighted_band(
    surgery_pool: dict[str, list[str]],
    weighting: dict[str, int | float],
) -> str | None:
    weighted_bands: list[tuple[str, float]] = []
    for band in SURGERY_BAND_ORDER:
        entries = surgery_pool.get(band, [])
        weight = float(weighting.get(band, 0))
        if entries and weight > 0:
            weighted_bands.append((band, weight))
    if not weighted_bands:
        return None
    if len(weighted_bands) == 1:
        return weighted_bands[0][0]
    return random.choices(
        [band for band, _ in weighted_bands],
        weights=[weight for _, weight in weighted_bands],
        k=1,
    )[0]


def _resolve_case_for_refresh(
    case_entry: dict[str, Any],
    surgery_weighting: dict[str, int | float],
) -> dict[str, Any]:
    resolved_case = dict(case_entry)
    surgery_pool = case_entry.get("surgery_pool")
    if surgery_pool:
        selected_band = _pick_weighted_band(surgery_pool, surgery_weighting)
        if selected_band:
            resolved_case["surgery_type"] = random.choice(surgery_pool[selected_band])
            resolved_case["surgery_probability_band"] = selected_band
            resolved_case["surgery_probability_weights"] = dict(surgery_weighting)
    postop_day_weights = case_entry.get("postop_day_weights")
    if isinstance(postop_day_weights, dict):
        day_candidates: list[str] = []
        day_weights: list[float] = []
        for day in POSTOP_DAY_ORDER:
            raw_weight = postop_day_weights.get(day, postop_day_weights.get(int(day), 0))
            weight = float(raw_weight)
            if weight > 0:
                day_candidates.append(day)
                day_weights.append(weight)
        if day_candidates:
            selected_day = random.choices(day_candidates, weights=day_weights, k=1)[0]
            selected_day_int = int(selected_day)
            resolved_case["postop_day"] = selected_day_int
            day_start_minutes = selected_day_int * MINUTES_PER_DAY
            day_end_minutes = day_start_minutes + MINUTES_PER_DAY
            resolved_case["simulated_elapsed_minutes"] = random.randint(day_start_minutes, day_end_minutes - 1)
            resolved_case["postop_day_probability_weights"] = {
                str(day): float(postop_day_weights.get(day, postop_day_weights.get(int(day), 0)))
                for day in POSTOP_DAY_ORDER
                if float(postop_day_weights.get(day, postop_day_weights.get(int(day), 0))) > 0
            }
            resolved_case["observed_at_label"] = f"J{selected_day_int}"
    label_template = resolved_case.get("case_label_template")
    if label_template:
        resolved_case["case_label"] = label_template.format(
            surgery_type=resolved_case["surgery_type"]
        )
    return resolved_case


def _build_refresh_assignments(
    simulation_config_path: Path,
    cases_catalog_path: Path,
    patient_ids: list[str],
) -> list[dict[str, Any]]:
    case_catalog = json.loads(cases_catalog_path.read_text(encoding="utf-8"))
    scenario_labels = _scenario_labels(simulation_config_path)
    surgery_weighting = case_catalog.get(
        "surgery_weighting",
        {"strong": 70, "medium": 20, "weak": 10},
    )
    stable_reference_case_id = case_catalog.get("stable_reference_case_id")
    cases = case_catalog.get("cases", [])
    stable_cases = [case for case in cases if case["case_id"] == stable_reference_case_id]
    dynamic_cases = [case for case in cases if case["case_id"] != stable_reference_case_id]
    if not stable_cases:
        raise ValueError("No healthy reference case configured for refresh")
    if not dynamic_cases:
        raise ValueError("No dynamic clinical case configured for refresh")

    patient_zero_id = "PAT-001" if "PAT-001" in patient_ids else None
    shuffled_patient_ids = [patient_id for patient_id in patient_ids if patient_id != patient_zero_id]
    random.shuffle(shuffled_patient_ids)
    random.shuffle(dynamic_cases)

    assignments: list[dict[str, Any]] = []
    stable_case = _resolve_case_for_refresh(stable_cases[0], surgery_weighting)
    if patient_zero_id:
        assignments.append(
            {
                "patient_id": patient_zero_id,
                **stable_case,
                "scenario_label": scenario_labels.get(stable_case["scenario"], stable_case["scenario"]),
                "origin": "healthy_reference",
            }
        )
    elif patient_ids:
        assignments.append(
            {
                "patient_id": patient_ids[0],
                **stable_case,
                "scenario_label": scenario_labels.get(stable_case["scenario"], stable_case["scenario"]),
                "origin": "healthy_reference",
            }
        )

    for index, patient_id in enumerate(shuffled_patient_ids, start=0):
        case_entry = _resolve_case_for_refresh(
            dynamic_cases[index % len(dynamic_cases)],
            surgery_weighting,
        )
        assignments.append(
            {
                "patient_id": patient_id,
                **case_entry,
                "scenario_label": scenario_labels.get(case_entry["scenario"], case_entry["scenario"]),
                "origin": case_entry.get("source", "case_catalog"),
            }
        )

    return assignments


def _default_monitoring_level() -> str:
    return "surveillance_postop"


def _sanitize_patient_identity(patient: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(patient)
    sanitized["full_name"] = sanitized["id"]
    return sanitized


def _sanitize_assignment_identity(assignment: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(assignment)
    sanitized["full_name"] = sanitized["patient_id"]
    return sanitized


@router.get("")
def list_patients(request: Request):
    services = request.app.state.services
    items = []
    for patient in services.postgres.list_patients():
        patient["last_vitals"] = services.last_vitals.get(patient["id"])
        items.append(_sanitize_patient_identity(patient))
    return items


@router.get("/{patient_id}")
def get_patient(patient_id: str, request: Request):
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient["last_vitals"] = services.last_vitals.get(patient_id)
    return _sanitize_patient_identity(patient)


@router.get("/{patient_id}/last-vitals")
def patient_last_vitals(patient_id: str, request: Request):
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    vitals = services.last_vitals.get(patient_id)
    if not vitals:
        raise HTTPException(status_code=404, detail="No vitals yet")
    return vitals


@router.post("/refresh")
async def refresh_patients(request: Request):
    services = request.app.state.services
    patient_ids = [patient["id"] for patient in services.postgres.list_patients()]
    if not patient_ids:
        raise HTTPException(status_code=400, detail="No patients available")
    try:
        assignments = _build_refresh_assignments(
            services.settings.simulation_config_path,
            services.settings.cases_catalog_path,
            patient_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    for patient_id in patient_ids:
        services.influx.clear_patient_history(patient_id)
        services.postgres.clear_patient_alerts(patient_id)
        services.postgres.clear_patient_notifications(patient_id)
        services.state.clear_patient(patient_id)
        services.last_vitals.pop(patient_id, None)
    await services.ws_manager.broadcast(notifications_reset_event(patient_ids))
    if not services.settings.test_mode:
        services.consumer.publish_refresh_request(assignments)

    for assignment in assignments:
            services.postgres.update_patient_case(
                patient_id=str(assignment["patient_id"]),
                payload={
                    "full_name": assignment["full_name"],
                    "profile": assignment["profile"],
                    "surgery_type": assignment["surgery_type"],
                    "postop_day": assignment["postop_day"],
                    "risk_level": assignment.get("risk_level", _default_monitoring_level()),
                    "room": assignment["room"],
                    "history": assignment.get("history", []),
                },
            )

    return {
        "status": "requested",
        "mode": "clinical-case-refresh",
        "rule": "PAT-001 reste le patient temoin en Constantes Normales, les 4 autres slots tirent des cas cliniques complets coherents depuis le catalogue",
        "assignments": [_sanitize_assignment_identity(assignment) for assignment in assignments],
    }
