from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.ml.features import (
    compute_evolving_risk,
    compute_immediate_criticality,
    derive_course_features,
)


router = APIRouter(prefix="/api/ml", tags=["ml"])


class MLFeedbackRequest(BaseModel):
    decision: Literal["validate", "invalidate"] = "validate"
    target: Literal["critical", "non_critical"] | None = None
    pathology: str | None = None
    diagnosis_decision: Literal["validated", "rejected"] | None = None
    final_diagnosis: str | None = None
    alert_id: int | None = None
    comment: str = Field(default="", max_length=500)


def _current_alert_snapshot(services, last_vitals: dict) -> tuple[int, int]:
    thresholds = services.alert_engine.ruleset.get("thresholds", {})
    hr = float(last_vitals.get("hr", 0))
    spo2 = float(last_vitals.get("spo2", 0))
    temp = float(last_vitals.get("temp", 0))
    map_value = float(last_vitals.get("map", 0))
    rr = float(last_vitals.get("rr", 0))
    shock_index = float(last_vitals.get("shock_index", 0))

    active_flags = [
        spo2 <= float(thresholds.get("spo2", {}).get("info", 94)),
        hr >= float(thresholds.get("hr", {}).get("info", 105)),
        rr >= float(thresholds.get("rr", {}).get("info", 22)),
        temp >= float(thresholds.get("temp", {}).get("info", 38.0)),
        map_value < float(thresholds.get("map", {}).get("warning", 70)),
        shock_index >= float(thresholds.get("shock_index", {}).get("warning", 0.9)),
    ]
    has_critical = int(
        spo2 < float(thresholds.get("spo2", {}).get("critical", 90))
        or hr >= float(thresholds.get("hr", {}).get("critical", 135))
        or rr >= float(thresholds.get("rr", {}).get("critical", 30))
        or temp >= float(thresholds.get("temp", {}).get("critical", 39.0))
        or temp <= float(thresholds.get("temp", {}).get("low_critical", 36.0))
        or map_value < float(thresholds.get("map", {}).get("critical", 65))
        or shock_index >= float(thresholds.get("shock_index", {}).get("critical", 1.0))
    )
    return sum(1 for flag in active_flags if flag), has_critical


def _build_ml_sample(services, patient_id: str) -> tuple[dict, dict, dict, list[dict]]:
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    last_vitals = services.last_vitals.get(patient_id)
    if not last_vitals:
        raise HTTPException(status_code=404, detail="No vitals yet")
    history_points = services.influx.query_history(patient_id=patient_id, metric="all", hours=0)
    pathology = (
        last_vitals.get("scenario_label")
        or last_vitals.get("scenario")
        or patient.get("scenario")
        or "Cas clinique non renseigne"
    )
    alert_count, has_critical = _current_alert_snapshot(services, last_vitals)
    course_features = derive_course_features(history_points)
    sample = {
        "timestamp": last_vitals["ts"],
        "patient_id": patient_id,
        "room": last_vitals.get("room", patient["room"]),
        "scenario": last_vitals.get("scenario", ""),
        "profile": last_vitals.get("profile", patient["profile"]),
        "pathology": pathology,
        "surgery_type": last_vitals.get("surgery_type", patient["surgery_type"]),
        "heart_rate": last_vitals.get("hr", 0),
        "spo2": last_vitals.get("spo2", 0),
        "temperature": last_vitals.get("temp", 0),
        "systolic_bp": last_vitals.get("sbp", 0),
        "diastolic_bp": last_vitals.get("dbp", 0),
        "respiratory_rate": last_vitals.get("rr", 0),
        "alert_count": alert_count,
        "has_critical": has_critical,
        **course_features,
    }
    return patient, last_vitals, sample, history_points


@router.get("/{patient_id}/predict")
def predict_patient_criticity(patient_id: str, request: Request):
    services = request.app.state.services
    patient, last_vitals, sample, history_points = _build_ml_sample(services, patient_id)
    probability = services.ml_service.predict(sample)
    thresholds = services.alert_engine.ruleset.get("thresholds", {})
    immediate_criticality = compute_immediate_criticality(last_vitals, thresholds)
    evolving_risk = compute_evolving_risk(
        history_points,
        thresholds,
        scenario_key=str(last_vitals.get("scenario", "")),
        pathology=str(sample["pathology"]),
    )
    return {
        "patient_id": patient_id,
        "patient_name": patient_id,
        "pathology": sample["pathology"],
        "probability": probability,
        "ml_probability": probability,
        "model_ready": probability is not None,
        "sample": sample,
        "last_vitals": last_vitals,
        "history_points": len(history_points),
        "course_window": "J0_to_now",
        "immediate_criticality": immediate_criticality,
        "evolving_risk": evolving_risk,
        "recent_feedback": services.postgres.list_ml_feedback(
            pathology=sample["pathology"],
            surgery_type=sample["surgery_type"],
            limit=5,
        ),
    }


@router.get("/feedback")
def list_ml_feedback(
    request: Request,
    patient_id: str | None = None,
    pathology: str | None = None,
    surgery_type: str | None = None,
    limit: int = 50,
):
    services = request.app.state.services
    return services.postgres.list_ml_feedback(
        patient_id=patient_id,
        pathology=pathology,
        surgery_type=surgery_type,
        limit=limit,
    )


@router.post("/train")
def train_criticity_model(request: Request):
    services = request.app.state.services
    try:
        metrics = services.ml_service.train()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "trained", **metrics}


@router.post("/{patient_id}/feedback")
def store_ml_feedback(patient_id: str, payload: MLFeedbackRequest, request: Request):
    services = request.app.state.services
    _, _, sample, _ = _build_ml_sample(services, patient_id)
    if payload.pathology:
        sample["pathology"] = payload.pathology

    current_label = int(sample["has_critical"])
    if payload.target == "critical":
        effective_label = 1
    elif payload.target == "non_critical":
        effective_label = 0
    elif payload.decision == "validate":
        effective_label = current_label
    else:
        effective_label = 0 if current_label else 1

    services.ml_service.append_feedback(sample, effective_label)
    stored_feedback = services.postgres.store_ml_feedback(
        patient_id=patient_id,
        label=f"{payload.decision}:{'critical' if effective_label else 'non_critical'}",
        comment=payload.comment,
        alert_id=payload.alert_id,
        pathology=sample["pathology"],
        diagnosis_decision=payload.diagnosis_decision,
        final_diagnosis=payload.final_diagnosis,
        surgery_type=sample["surgery_type"],
        has_critical=effective_label,
    )
    return {
        "status": "stored",
        "patient_id": patient_id,
        "pathology": sample["pathology"],
        "has_critical": effective_label,
        "feedback": stored_feedback,
    }
