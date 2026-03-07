from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.llm.prompt_templates import SCENARIO_REVIEW_SYSTEM_PROMPT, build_scenario_review_prompt


router = APIRouter(prefix="/api/llm", tags=["llm"])


SCENARIO_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "scenario_confirmed": {"type": "boolean"},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "primary_hypothesis": {"type": "string"},
        "alternatives": {"type": "array", "items": {"type": "string"}},
        "supporting_signals": {"type": "array", "items": {"type": "string"}},
        "contradicting_signals": {"type": "array", "items": {"type": "string"}},
        "clinical_priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "recommended_action": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": [
        "scenario_confirmed",
        "confidence",
        "primary_hypothesis",
        "alternatives",
        "supporting_signals",
        "contradicting_signals",
        "clinical_priority",
        "recommended_action",
        "note",
    ],
}


class ScenarioReviewResponse(BaseModel):
    source: Literal["ollama", "rule-based"]
    scenario: str
    surgery_type: str
    scenario_confirmed: bool
    confidence: int = Field(ge=0, le=100)
    primary_hypothesis: str
    alternatives: list[str]
    supporting_signals: list[str]
    contradicting_signals: list[str]
    clinical_priority: Literal["low", "medium", "high"]
    recommended_action: str
    note: str


def _current_scenario_name(last_vitals: dict, patient: dict) -> str:
    return (
        last_vitals.get("scenario_label")
        or last_vitals.get("scenario")
        or patient.get("scenario")
        or "Cas clinique non renseigne"
    )


@router.get("/{patient_id}/scenario-review")
async def scenario_review(patient_id: str, request: Request):
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    last_vitals = services.last_vitals.get(patient_id)
    if not last_vitals:
        raise HTTPException(status_code=404, detail="No vitals yet")

    scenario = _current_scenario_name(last_vitals, patient)
    surgery_type = last_vitals.get("surgery_type", patient["surgery_type"])
    alerts = services.postgres.list_alerts(
        patient_id=patient_id,
        pathology=scenario,
        surgery_type=surgery_type,
        limit=5,
    )
    recent_points = services.influx.query_history(patient_id=patient_id, metric="all", hours=24)
    prompt = build_scenario_review_prompt(patient, last_vitals, alerts, recent_points)
    structured = await services.llm_client.generate_structured(
        prompt,
        SCENARIO_REVIEW_SCHEMA,
        system=SCENARIO_REVIEW_SYSTEM_PROMPT,
    )
    if structured:
        try:
            normalized = _normalize_structured_review(
                structured,
                scenario=scenario,
                surgery_type=surgery_type,
            )
            return ScenarioReviewResponse.model_validate({"source": "ollama", **normalized})
        except Exception:
            pass
    return ScenarioReviewResponse.model_validate(_fallback_review(patient, last_vitals, alerts))


def _normalize_structured_review(
    payload: dict,
    *,
    scenario: str,
    surgery_type: str,
) -> dict:
    def _string_list(value: object, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback

    try:
        confidence = int(round(float(payload.get("confidence", 50))))
    except (TypeError, ValueError):
        confidence = 50

    clinical_priority = str(payload.get("clinical_priority", "low")).strip().lower()
    if clinical_priority not in {"low", "medium", "high"}:
        clinical_priority = "low"

    scenario_confirmed = payload.get("scenario_confirmed", False)
    if not isinstance(scenario_confirmed, bool):
        scenario_confirmed = str(scenario_confirmed).strip().lower() in {"1", "true", "yes", "oui"}

    confidence = max(0, min(100, confidence))
    if confidence == 0:
        confidence = 60 if scenario_confirmed else 40

    return {
        "scenario": scenario,
        "surgery_type": surgery_type,
        "scenario_confirmed": scenario_confirmed,
        "confidence": confidence,
        "primary_hypothesis": str(payload.get("primary_hypothesis", scenario)).strip() or scenario,
        "alternatives": _string_list(payload.get("alternatives"), [scenario]),
        "supporting_signals": _string_list(
            payload.get("supporting_signals"),
            ["pas d'argument fort detecte automatiquement"],
        ),
        "contradicting_signals": _string_list(
            payload.get("contradicting_signals"),
            ["pas de contradiction majeure detectee"],
        ),
        "clinical_priority": clinical_priority,
        "recommended_action": str(payload.get("recommended_action", "")).strip()
        or "Poursuivre la surveillance et reevaluer si les constantes se degradent.",
        "note": str(payload.get("note", "")).strip()
        or "Aide a l'orientation clinique uniquement, ne remplace pas une decision medicale.",
    }


def _fallback_review(patient: dict, last_vitals: dict, alerts: list[dict]) -> dict:
    scenario = _current_scenario_name(last_vitals, patient)
    surgery_type = last_vitals.get("surgery_type", patient["surgery_type"])
    supporting_signals: list[str] = []
    contradicting_signals: list[str] = []
    alternatives: list[str] = []

    hr = float(last_vitals.get("hr", 0))
    spo2 = float(last_vitals.get("spo2", 0))
    sbp = float(last_vitals.get("sbp", 0))
    rr = float(last_vitals.get("rr", 0))
    temp = float(last_vitals.get("temp", 0))
    map_value = int(round(float(last_vitals.get("map", 0))))

    if spo2 < 92:
        supporting_signals.append(f"SpO2 basse a {int(spo2)}%")
    if rr >= 22:
        supporting_signals.append(f"FR elevee a {int(rr)}/min")
    if hr >= 110:
        supporting_signals.append(f"FC elevee a {int(hr)} bpm")
    if sbp < 90 or map_value < 65:
        supporting_signals.append(f"instabilite hemodynamique avec SBP {int(sbp)} et TAM {map_value}")
    if temp >= 38.0 or temp <= 36.0:
        supporting_signals.append(f"temperature anormale a {temp:.1f} C")

    if spo2 >= 95:
        contradicting_signals.append(f"oxygenation preservee a {int(spo2)}%")
    if hr < 100:
        contradicting_signals.append(f"FC non franchement critique a {int(hr)} bpm")
    if sbp >= 100 and map_value >= 70:
        contradicting_signals.append(f"hemodynamique encore compensee avec TAM {map_value}")
    if 36.0 < temp < 38.0:
        contradicting_signals.append(f"temperature sans anomalie majeure a {temp:.1f} C")

    if "pneumopathie" in scenario.lower() or "ira" in scenario.lower():
        alternatives = ["embolie pulmonaire", "hypoventilation post-op"]
    elif "sepsis" in scenario.lower():
        alternatives = ["hypovolemie", "complication infectieuse locale"]
    elif "hemorragie" in scenario.lower():
        alternatives = ["choc hypovolemique", "sepsis avec hypotension"]
    elif "embolie" in scenario.lower():
        alternatives = ["pneumopathie", "IRA post-op"]
    else:
        alternatives = ["complication respiratoire", "complication hemodynamique"]

    critical_alert = any(alert["level"] == "CRITICAL" for alert in alerts)
    warning_alert = any(alert["level"] == "WARNING" for alert in alerts)
    if critical_alert:
        clinical_priority = "high"
        confidence = 80 if supporting_signals else 65
    elif warning_alert:
        clinical_priority = "medium"
        confidence = 65 if supporting_signals else 50
    else:
        clinical_priority = "low"
        confidence = 55 if supporting_signals else 35

    scenario_confirmed = len(supporting_signals) >= len(contradicting_signals)
    recommended_action = {
        "high": "Reevaluation medicale rapide, verification des alertes critiques et surveillance rapprochee.",
        "medium": "Surveillance rapprochee et confirmation clinique du scenario.",
        "low": "Poursuivre la surveillance et reevaluer si les constantes se degradent.",
    }[clinical_priority]

    return {
        "source": "rule-based",
        "scenario": scenario,
        "surgery_type": surgery_type,
        "scenario_confirmed": scenario_confirmed,
        "confidence": confidence,
        "primary_hypothesis": scenario,
        "alternatives": alternatives,
        "supporting_signals": supporting_signals or ["pas d'argument fort detecte automatiquement"],
        "contradicting_signals": contradicting_signals or ["pas de contradiction majeure detectee"],
        "clinical_priority": clinical_priority,
        "recommended_action": recommended_action,
        "note": "Aide a l'orientation clinique uniquement, ne remplace pas une decision medicale.",
    }
