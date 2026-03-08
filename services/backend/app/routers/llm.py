from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.llm.clinical_context import ClinicalContextPayload
from app.llm.prompt_templates import (
    CLINICAL_PACKAGE_SYSTEM_PROMPT,
    PRIORITIZATION_SYSTEM_PROMPT,
    SCENARIO_REVIEW_SYSTEM_PROMPT,
    build_clinical_package_prompt,
    build_prioritization_prompt,
    build_scenario_review_prompt,
)


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
    llm_status: Literal["ollama", "rule-based", "llm-unavailable", "disabled"] = "rule-based"
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


CLINICAL_PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "structured_synthesis": {"type": "string"},
        "alert_explanations": {"type": "array", "items": {"type": "string"}},
        "hypothesis_ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "compatibility": {"type": "string", "enum": ["high", "medium", "low"]},
                    "arguments_for": {"type": "array", "items": {"type": "string"}},
                    "arguments_against": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["label", "compatibility", "arguments_for", "arguments_against"],
            },
        },
        "trajectory_status": {"type": "string", "enum": ["stable", "worsening", "switching", "recovering"]},
        "trajectory_explanation": {"type": "string"},
        "recheck_recommendations": {"type": "array", "items": {"type": "string"}},
        "handoff_summary": {"type": "string"},
        "scenario_consistency": {"type": "string"},
    },
    "required": [
        "structured_synthesis",
        "alert_explanations",
        "hypothesis_ranking",
        "trajectory_status",
        "trajectory_explanation",
        "recheck_recommendations",
        "handoff_summary",
        "scenario_consistency",
    ],
}


PRIORITIZATION_SCHEMA = {
    "type": "object",
    "properties": {
        "prioritized_patients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "priority_rank": {"type": "integer"},
                    "priority_level": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reason": {"type": "string"},
                },
                "required": ["patient_id", "priority_rank", "priority_level", "reason"],
            },
        }
    },
    "required": ["prioritized_patients"],
}


class HypothesisRow(BaseModel):
    label: str
    compatibility: Literal["high", "medium", "low"]
    arguments_for: list[str]
    arguments_against: list[str]


class ClinicalPackageResponse(BaseModel):
    source: Literal["ollama", "rule-based"]
    llm_status: Literal["ollama", "rule-based", "llm-unavailable", "disabled"] = "rule-based"
    patient_id: str
    structured_synthesis: str
    alert_explanations: list[str]
    hypothesis_ranking: list[HypothesisRow]
    trajectory_status: Literal["stable", "worsening", "switching", "recovering"]
    trajectory_explanation: str
    recheck_recommendations: list[str]
    handoff_summary: str
    scenario_consistency: str


class PrioritizationRow(BaseModel):
    patient_id: str
    priority_rank: int
    priority_level: Literal["high", "medium", "low"]
    reason: str


class PrioritizationResponse(BaseModel):
    source: Literal["ollama", "rule-based"]
    llm_status: Literal["ollama", "rule-based", "llm-unavailable", "disabled"] = "rule-based"
    prioritized_patients: list[PrioritizationRow]


class QuestionnaireOptionResponse(BaseModel):
    value: str
    label: str


class QuestionnaireQuestionResponse(BaseModel):
    id: str
    label: str
    type: str
    options: list[QuestionnaireOptionResponse]


class QuestionnaireModuleResponse(BaseModel):
    id: str
    title: str
    description: str
    targets: list[str]
    matched_triggers: list[str]
    source_refs: list[dict[str, str]]
    questions: list[QuestionnaireQuestionResponse]


class QuestionnaireSelectionResponse(BaseModel):
    patient_id: str
    trigger_summary: list[str]
    modules: list[QuestionnaireModuleResponse]


def _current_scenario_name(last_vitals: dict, patient: dict) -> str:
    return (
        last_vitals.get("scenario_label")
        or last_vitals.get("scenario")
        or patient.get("scenario")
        or "Cas clinique non renseigne"
    )


def _load_patient_bundle(
    patient_id: str,
    request: Request,
    *,
    restrict_to_scenario: bool = False,
) -> tuple[object, dict, dict, str, str, list[dict], list[dict]]:
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    last_vitals = services.last_vitals.get(patient_id)
    if not last_vitals:
        raise HTTPException(status_code=404, detail="No vitals yet")
    scenario = _current_scenario_name(last_vitals, patient)
    surgery_type = last_vitals.get("surgery_type", patient["surgery_type"])
    if restrict_to_scenario:
        alerts = services.postgres.list_alerts(
            patient_id=patient_id,
            pathology=scenario,
            surgery_type=surgery_type,
            limit=5,
        )
    else:
        alerts = services.postgres.list_alerts(
            patient_id=patient_id,
            limit=5,
        )
    history_points = services.influx.query_history(patient_id=patient_id, metric="all", hours=0)
    return services, patient, last_vitals, scenario, surgery_type, alerts, history_points


def _prompt_context_from_payload(services: object, payload: ClinicalContextPayload) -> dict[str, Any]:
    prompt_context = payload.as_prompt_dict()
    questionnaire_payload = prompt_context.get("questionnaire")
    if questionnaire_payload and getattr(services, "questionnaire_engine", None):
        prompt_context["questionnaire"] = services.questionnaire_engine.enrich_answers(
            questionnaire_payload.get("answers", []),
            responder=str(questionnaire_payload.get("responder") or "patient"),
            comment=str(questionnaire_payload.get("comment") or ""),
        )
    return prompt_context


@router.get("/{patient_id}/scenario-review")
async def scenario_review(patient_id: str, request: Request):
    return await _scenario_review_with_context(patient_id, request, ClinicalContextPayload())


@router.post("/{patient_id}/scenario-review")
async def scenario_review_with_context(
    patient_id: str,
    payload: ClinicalContextPayload,
    request: Request,
):
    return await _scenario_review_with_context(patient_id, request, payload)


async def _scenario_review_with_context(
    patient_id: str,
    request: Request,
    payload: ClinicalContextPayload,
):
    services, patient, last_vitals, scenario, surgery_type, alerts, recent_points = _load_patient_bundle(
        patient_id,
        request,
        restrict_to_scenario=True,
    )
    prompt = build_scenario_review_prompt(
        patient,
        last_vitals,
        alerts,
        recent_points,
        schema=SCENARIO_REVIEW_SCHEMA,
        clinical_context=_prompt_context_from_payload(services, payload),
        knowledge_excerpt=services.knowledge_base.get_excerpt("scenario_review"),
    )
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
            return ScenarioReviewResponse.model_validate({"source": "ollama", "llm_status": "ollama", **normalized})
        except Exception:
            pass
    fallback = _fallback_review(patient, last_vitals, alerts)
    fallback["llm_status"] = "llm-unavailable" if services.settings.enable_llm else "disabled"
    return ScenarioReviewResponse.model_validate(fallback)


@router.get("/{patient_id}/clinical-package")
async def clinical_package(patient_id: str, request: Request):
    return await _clinical_package_with_context(patient_id, request, ClinicalContextPayload())


@router.post("/{patient_id}/clinical-package")
async def clinical_package_with_context(
    patient_id: str,
    payload: ClinicalContextPayload,
    request: Request,
):
    return await _clinical_package_with_context(patient_id, request, payload)


async def _clinical_package_with_context(
    patient_id: str,
    request: Request,
    payload: ClinicalContextPayload,
):
    services, patient, last_vitals, scenario, surgery_type, alerts, history_points = _load_patient_bundle(
        patient_id,
        request,
        restrict_to_scenario=False,
    )
    prompt = build_clinical_package_prompt(
        patient,
        last_vitals,
        alerts,
        history_points,
        schema=CLINICAL_PACKAGE_SCHEMA,
        clinical_context=_prompt_context_from_payload(services, payload),
        knowledge_excerpt=services.knowledge_base.get_excerpt("clinical_package"),
    )
    structured = await services.llm_client.generate_structured(
        prompt,
        CLINICAL_PACKAGE_SCHEMA,
        system=CLINICAL_PACKAGE_SYSTEM_PROMPT,
    )
    if structured:
        try:
            normalized = _normalize_clinical_package(structured, patient_id=patient_id)
            return ClinicalPackageResponse.model_validate({"source": "ollama", "llm_status": "ollama", **normalized})
        except Exception:
            pass
    fallback = _fallback_clinical_package(patient, last_vitals, alerts, history_points, surgery_type)
    return ClinicalPackageResponse.model_validate(
        {
            "source": "rule-based",
            "llm_status": "llm-unavailable" if services.settings.enable_llm else "disabled",
            **fallback,
        }
    )


@router.get("/prioritize/patients")
async def prioritize_patients(request: Request):
    services = request.app.state.services
    patients = services.postgres.list_patients()
    snapshots: list[dict] = []
    for patient in patients:
        last_vitals = services.last_vitals.get(patient["id"])
        if not last_vitals:
            continue
        alerts = services.postgres.list_alerts(
            patient_id=patient["id"],
            limit=3,
        )
        snapshots.append(
            {
                "patient_id": patient["id"],
                "surgery_type": last_vitals.get("surgery_type", patient["surgery_type"]),
                "postop_day": last_vitals.get("postop_day", patient["postop_day"]),
                "last_vitals": {
                    "hr": last_vitals.get("hr"),
                    "spo2": last_vitals.get("spo2"),
                    "map": last_vitals.get("map"),
                    "rr": last_vitals.get("rr"),
                    "temp": last_vitals.get("temp"),
                    "shock_index": last_vitals.get("shock_index"),
                },
                "alert_levels": [alert["level"] for alert in alerts],
            }
        )
    prompt = build_prioritization_prompt(
        snapshots,
        knowledge_excerpt=services.knowledge_base.get_excerpt("prioritization"),
    )
    structured = await services.llm_client.generate_structured(
        prompt,
        PRIORITIZATION_SCHEMA,
        system=PRIORITIZATION_SYSTEM_PROMPT,
    )
    if structured:
        try:
            normalized = _normalize_prioritization(structured, snapshots)
            return PrioritizationResponse.model_validate(
                {"source": "ollama", "llm_status": "ollama", "prioritized_patients": normalized}
            )
        except Exception:
            pass
    fallback = _fallback_prioritization(snapshots)
    return PrioritizationResponse.model_validate(
        {
            "source": "rule-based",
            "llm_status": "llm-unavailable" if services.settings.enable_llm else "disabled",
            "prioritized_patients": fallback,
        }
    )


@router.get("/{patient_id}/questionnaire")
async def differential_questionnaire(patient_id: str, request: Request):
    services, patient, last_vitals, _scenario, _surgery_type, alerts, history_points = _load_patient_bundle(
        patient_id,
        request,
        restrict_to_scenario=False,
    )
    selection = services.questionnaire_engine.select_modules(
        last_vitals=last_vitals,
        alerts=alerts,
        history_points=history_points,
    )
    return QuestionnaireSelectionResponse.model_validate(
        {
            "patient_id": patient["id"],
            "trigger_summary": selection.trigger_summary,
            "modules": selection.modules,
        }
    )


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


def _normalize_clinical_package(payload: dict, *, patient_id: str) -> dict:
    def _string_list(value: object, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback

    def _normalize_hypothesis_rows(rows: object) -> list[dict]:
        if not isinstance(rows, list):
            return []
        normalized: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            compatibility = str(row.get("compatibility", "low")).strip().lower()
            if compatibility not in {"high", "medium", "low"}:
                compatibility = "low"
            normalized.append(
                {
                    "label": str(row.get("label", "Hypothese non precisee")).strip() or "Hypothese non precisee",
                    "compatibility": compatibility,
                    "arguments_for": _string_list(row.get("arguments_for"), ["argument non detaille"]),
                    "arguments_against": _string_list(row.get("arguments_against"), ["pas d'element contradictoire majeur"]),
                }
            )
        return normalized[:3]

    trajectory_status = str(payload.get("trajectory_status", "stable")).strip().lower()
    if trajectory_status not in {"stable", "worsening", "switching", "recovering"}:
        trajectory_status = "stable"

    return {
        "patient_id": patient_id,
        "structured_synthesis": str(payload.get("structured_synthesis", "")).strip() or "Synthese non disponible.",
        "alert_explanations": _string_list(
            payload.get("alert_explanations"),
            ["Pas d'explication supplementaire disponible pour les alertes."],
        ),
        "hypothesis_ranking": _normalize_hypothesis_rows(payload.get("hypothesis_ranking")),
        "trajectory_status": trajectory_status,
        "trajectory_explanation": str(payload.get("trajectory_explanation", "")).strip()
        or "Evolution insuffisamment detaillee.",
        "recheck_recommendations": _string_list(
            payload.get("recheck_recommendations"),
            ["Poursuivre la surveillance des constantes et reevaluer si aggravation."],
        ),
        "handoff_summary": str(payload.get("handoff_summary", "")).strip() or "Transmission non disponible.",
        "scenario_consistency": str(payload.get("scenario_consistency", "")).strip()
        or "Coherence de scenario non detaillee.",
    }


def _normalize_prioritization(payload: dict, snapshots: list[dict]) -> list[dict]:
    valid_ids = {snapshot["patient_id"] for snapshot in snapshots}
    rows = payload.get("prioritized_patients")
    if not isinstance(rows, list):
        return []
    normalized: list[dict] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        patient_id = str(row.get("patient_id", "")).strip()
        if not patient_id or patient_id not in valid_ids or patient_id in seen_ids:
            continue
        priority_level = str(row.get("priority_level", "low")).strip().lower()
        if priority_level not in {"high", "medium", "low"}:
            priority_level = "low"
        normalized.append(
            {
                "patient_id": patient_id,
                "priority_rank": int(row.get("priority_rank") or index),
                "priority_level": priority_level,
                "reason": str(row.get("reason", "Priorisation non detaillee.")).strip()
                or "Priorisation non detaillee.",
            }
        )
        seen_ids.add(patient_id)
    return normalized


def _history_delta(history_points: list[dict], key: str, current_value: float) -> float:
    if not history_points:
        return 0.0
    start = history_points[0].get("values", {})
    return current_value - float(start.get(key, current_value))


def _objective_hypothesis_rows(
    last_vitals: dict,
    alerts: list[dict],
    history_points: list[dict],
) -> list[dict]:
    hr = float(last_vitals.get("hr", 0))
    spo2 = float(last_vitals.get("spo2", 0))
    sbp = float(last_vitals.get("sbp", 0))
    rr = float(last_vitals.get("rr", 0))
    temp = float(last_vitals.get("temp", 0))
    map_value = float(last_vitals.get("map", 0))
    shock_index = float(last_vitals.get("shock_index", 0) or 0)

    hr_delta = _history_delta(history_points, "hr", hr)
    spo2_delta = _history_delta(history_points, "spo2", spo2)
    map_delta = _history_delta(history_points, "map", map_value)
    temp_delta = _history_delta(history_points, "temp", temp)

    alert_blob = " ".join(
        f"{str(alert.get('title') or '')} {str(alert.get('message') or '')}".lower() for alert in alerts
    )

    candidates = [
        {
            "label": "Complication respiratoire post-op (pneumopathie / IRA)",
            "score": 0,
            "for": [],
            "against": [],
        },
        {
            "label": "Embolie pulmonaire possible",
            "score": 0,
            "for": [],
            "against": [],
        },
        {
            "label": "Sepsis / complication infectieuse possible",
            "score": 0,
            "for": [],
            "against": [],
        },
        {
            "label": "Hemorragie / hypovolemie possible",
            "score": 0,
            "for": [],
            "against": [],
        },
        {
            "label": "Douleur post-op non controlee possible",
            "score": 0,
            "for": [],
            "against": [],
        },
        {
            "label": "Complication cardiaque post-op possible",
            "score": 0,
            "for": [],
            "against": [],
        },
    ]

    def add(label: str, points: int, reason: str, *, against: bool = False) -> None:
        for candidate in candidates:
            if candidate["label"] == label:
                if against:
                    candidate["against"].append(reason)
                else:
                    candidate["score"] += points
                    candidate["for"].append(reason)
                return

    if spo2 < 94:
        add("Complication respiratoire post-op (pneumopathie / IRA)", 2, f"SpO2 basse a {int(spo2)}%.")
        add("Embolie pulmonaire possible", 2, f"SpO2 basse a {int(spo2)}%.")
    if rr >= 22:
        add("Complication respiratoire post-op (pneumopathie / IRA)", 2, f"FR elevee a {int(rr)}/min.")
        add("Embolie pulmonaire possible", 1, f"FR elevee a {int(rr)}/min.")
        add("Sepsis / complication infectieuse possible", 1, f"FR elevee a {int(rr)}/min.")
        add("Douleur post-op non controlee possible", 1, f"FR un peu elevee a {int(rr)}/min.")
    if hr >= 110:
        add("Embolie pulmonaire possible", 2, f"FC elevee a {int(hr)} bpm.")
        add("Sepsis / complication infectieuse possible", 1, f"FC elevee a {int(hr)} bpm.")
        add("Hemorragie / hypovolemie possible", 1, f"FC elevee a {int(hr)} bpm.")
        add("Complication cardiaque post-op possible", 1, f"FC elevee a {int(hr)} bpm.")
    if temp >= 38.0 or temp <= 36.0:
        add("Sepsis / complication infectieuse possible", 2, f"Temperature anormale a {temp:.1f} C.")
        add("Complication respiratoire post-op (pneumopathie / IRA)", 1, f"Temperature anormale a {temp:.1f} C.")
    if map_value < 70 or sbp < 90:
        add("Hemorragie / hypovolemie possible", 2, f"Hemodynamique basse avec SBP {int(sbp)} et TAM {int(round(map_value))}.")
        add("Complication cardiaque post-op possible", 2, f"Hemodynamique basse avec SBP {int(sbp)} et TAM {int(round(map_value))}.")
        add("Sepsis / complication infectieuse possible", 2, f"TAM basse a {int(round(map_value))} mmHg.")
        add("Embolie pulmonaire possible", 1, f"Retentissement hemodynamique avec TAM {int(round(map_value))}.")
    if shock_index >= 0.9:
        add("Hemorragie / hypovolemie possible", 2, f"Shock index eleve a {shock_index:.2f}.")
        add("Complication cardiaque post-op possible", 1, f"Shock index eleve a {shock_index:.2f}.")
        add("Embolie pulmonaire possible", 1, f"Shock index eleve a {shock_index:.2f}.")
    if spo2_delta <= -3:
        add("Complication respiratoire post-op (pneumopathie / IRA)", 2, f"SpO2 en baisse de {int(round(spo2_delta))} points depuis J0.")
        add("Embolie pulmonaire possible", 2, f"SpO2 en baisse de {int(round(spo2_delta))} points depuis J0.")
    if temp_delta >= 0.5:
        add("Sepsis / complication infectieuse possible", 2, f"Temperature en hausse de {temp_delta:.1f} C depuis J0.")
    if hr_delta >= 15 and map_delta <= -8:
        add("Hemorragie / hypovolemie possible", 3, f"FC {int(round(hr_delta)):+d} bpm et TAM {int(round(map_delta)):+d} depuis J0.")
    if hr_delta >= 8 and 36.0 < temp < 38.0 and spo2 >= 95 and map_value >= 85:
        add("Douleur post-op non controlee possible", 3, "Reponse sympathique sans hypoxemie ni fievre majeure.")
    if map_delta <= -8 and temp < 38.0:
        add("Complication cardiaque post-op possible", 2, f"TAM en baisse de {int(round(map_delta))} mmHg sans syndrome febrile majeur.")

    if "spo2" in alert_blob or "desaturation" in alert_blob or "resp" in alert_blob:
        add("Complication respiratoire post-op (pneumopathie / IRA)", 1, "Alertes recentes a dominante respiratoire.")
        add("Embolie pulmonaire possible", 1, "Alertes recentes a dominante respiratoire.")
    if "sepsis" in alert_blob or "temperature" in alert_blob:
        add("Sepsis / complication infectieuse possible", 1, "Alertes recentes compatibles avec un contexte infectieux.")
    if "shock" in alert_blob or "map" in alert_blob or "hemo" in alert_blob:
        add("Hemorragie / hypovolemie possible", 1, "Alertes recentes a dominante hemodynamique.")
        add("Complication cardiaque post-op possible", 1, "Alertes recentes a dominante hemodynamique.")

    if spo2 >= 95:
        add("Complication respiratoire post-op (pneumopathie / IRA)", 0, f"Oxygenation preservee a {int(spo2)}%.", against=True)
        add("Embolie pulmonaire possible", 0, f"Oxygenation preservee a {int(spo2)}%.", against=True)
    if 36.0 < temp < 38.0:
        add("Sepsis / complication infectieuse possible", 0, f"Temperature sans anomalie majeure a {temp:.1f} C.", against=True)
    if map_value >= 80:
        add("Hemorragie / hypovolemie possible", 0, f"Hemodynamique encore preservee avec TAM {int(round(map_value))}.", against=True)
        add("Complication cardiaque post-op possible", 0, f"Hemodynamique encore preservee avec TAM {int(round(map_value))}.", against=True)
    if spo2 < 94 or temp >= 38.0 or map_value < 70:
        add("Douleur post-op non controlee possible", 0, "Douleur isolee moins probable si hypoxemie, fievre ou hypotension.", against=True)

    def compatibility(score: int) -> str:
        if score >= 6:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    rows = [
        {
            "label": candidate["label"],
            "compatibility": compatibility(candidate["score"]),
            "arguments_for": candidate["for"][:3] or ["Peu d'arguments objectifs supplementaires."],
            "arguments_against": candidate["against"][:3] or ["Pas d'element contradictoire majeur releve."],
            "score": candidate["score"],
        }
        for candidate in candidates
        if candidate["score"] > 0
    ]
    rows.sort(key=lambda row: row["score"], reverse=True)
    if not rows:
        rows = [
            {
                "label": "Complication post-op a caracteriser",
                "compatibility": "low",
                "arguments_for": ["Les signaux actuels sont insuffisants pour orienter nettement une complication precise."],
                "arguments_against": ["Aucun pattern fort n'est objectivement dominant."],
                "score": 1,
            }
        ]
    return [{key: value for key, value in row.items() if key != "score"} for row in rows[:3]]


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


def _fallback_clinical_package(
    patient: dict,
    last_vitals: dict,
    alerts: list[dict],
    history_points: list[dict],
    surgery_type: str,
) -> dict:
    hypothesis_rows = _objective_hypothesis_rows(last_vitals, alerts, history_points)
    hr = float(last_vitals.get("hr", 0))
    spo2 = float(last_vitals.get("spo2", 0))
    rr = float(last_vitals.get("rr", 0))
    temp = float(last_vitals.get("temp", 0))
    map_value = int(round(float(last_vitals.get("map", 0))))
    trajectory_status = "stable"
    trajectory_explanation = "Pas d'aggravation nette detectee."
    if len(history_points) >= 2:
        start = history_points[0].get("values", {})
        hr_delta = float(last_vitals.get("hr", 0)) - float(start.get("hr", 0))
        spo2_delta = float(last_vitals.get("spo2", 0)) - float(start.get("spo2", 0))
        map_delta = float(last_vitals.get("map", 0)) - float(start.get("map", 0))
        if hr_delta >= 10 or spo2_delta <= -3 or map_delta <= -8:
            trajectory_status = "worsening"
            trajectory_explanation = (
                f"Depuis J0: FC {int(round(hr_delta)):+d} bpm, "
                f"SpO2 {int(round(spo2_delta)):+d} points, TAM {int(round(map_delta)):+d}."
            )
    if any(alert["level"] == "CRITICAL" for alert in alerts):
        trajectory_status = "switching"
        trajectory_explanation = "Bascule recente avec alertes critiques sur le patient."

    alert_explanations = []
    for alert in alerts[:3]:
        alert_explanations.append(
            f"{alert['title']}: {alert['message']} (niveau {alert['level']})."
        )
    if not alert_explanations:
        alert_explanations = ["Pas d'alerte active du patient a expliquer."]

    recheck_recommendations = []
    if spo2 < 94:
        recheck_recommendations.append("Recontroler SpO2 et FR rapidement.")
    if temp >= 38.0 or temp <= 36.0:
        recheck_recommendations.append("Recontroler temperature et evolution infectieuse.")
    if map_value < 70 or hr >= 110:
        recheck_recommendations.append("Recontroler hemodynamique et signes de bas debit.")
    if not recheck_recommendations:
        recheck_recommendations.append("Poursuivre la surveillance reguliere des constantes.")

    leading_hypothesis = hypothesis_rows[0]["label"]

    return {
        "patient_id": patient["id"],
        "structured_synthesis": (
            f"{patient['id']} apres {surgery_type}: tableau possible compatible avec {leading_hypothesis}, "
            f"avec FC {int(hr)} bpm, SpO2 {int(spo2)}%, TAM {map_value}, FR {int(rr)}/min, T C {temp:.1f}."
        ),
        "alert_explanations": alert_explanations,
        "hypothesis_ranking": hypothesis_rows[:3],
        "trajectory_status": trajectory_status,
        "trajectory_explanation": trajectory_explanation,
        "recheck_recommendations": recheck_recommendations[:3],
        "handoff_summary": (
            f"{patient['id']} J{last_vitals.get('postop_day', patient['postop_day'])} apres {surgery_type}, "
            f"hypothese dominante {leading_hypothesis}, alertes {len(alerts)}, surveillance actuelle a poursuivre."
        ),
        "scenario_consistency": "Le tableau clinique observe reste compatible avec l'hypothese principale proposee, sans acces au scenario simule interne.",
    }


def _fallback_prioritization(snapshots: list[dict]) -> list[dict]:
    scored: list[dict] = []
    for snapshot in snapshots:
        last_vitals = snapshot.get("last_vitals", {})
        levels = snapshot.get("alert_levels", [])
        score = 0
        if "CRITICAL" in levels:
            score += 50
        if "WARNING" in levels:
            score += 20
        if float(last_vitals.get("spo2") or 100) < 92:
            score += 20
        if float(last_vitals.get("map") or 999) < 70:
            score += 20
        if float(last_vitals.get("rr") or 0) >= 22:
            score += 10
        if float(last_vitals.get("temp") or 0) >= 38.0 or float(last_vitals.get("temp") or 99) <= 36.0:
            score += 8
        if float(last_vitals.get("shock_index") or 0) >= 0.9:
            score += 10
        scored.append(
            {
                "patient_id": snapshot["patient_id"],
                "score": score,
                "reason": (
                    f"Alertes {levels or ['aucune']}, SpO2 {last_vitals.get('spo2')}, "
                    f"TAM {last_vitals.get('map')}, FR {last_vitals.get('rr')}, T C {last_vitals.get('temp')}."
                ),
            }
        )

    scored.sort(key=lambda row: row["score"], reverse=True)
    prioritized: list[dict] = []
    for rank, row in enumerate(scored, start=1):
        if row["score"] >= 50:
            level = "high"
        elif row["score"] >= 20:
            level = "medium"
        else:
            level = "low"
        prioritized.append(
            {
                "patient_id": row["patient_id"],
                "priority_rank": rank,
                "priority_level": level,
                "reason": row["reason"],
            }
        )
    return prioritized
