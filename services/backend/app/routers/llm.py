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


def _history_value(point: dict, key: str, default: float = 0.0) -> float:
    values = point.get("values", {})
    try:
        return float(values.get(key, default))
    except (TypeError, ValueError):
        return default


def _first_metric_onset(
    history_points: list[dict],
    *,
    metric: str,
    baseline_value: float,
    threshold: float,
    direction: str,
) -> int | None:
    if len(history_points) < 2:
        return None
    for index, point in enumerate(history_points[1:], start=1):
        value = _history_value(point, metric, baseline_value)
        if direction == "rise" and value - baseline_value >= threshold:
            return index
        if direction == "drop" and baseline_value - value >= threshold:
            return index
        if direction == "abs" and abs(value - baseline_value) >= threshold:
            return index
    return None


def _temporal_profile(history_points: list[dict]) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "abrupt": False,
        "progressive": False,
        "fluctuating": False,
        "respiratory_first": False,
        "hemodynamic_first": False,
        "fever_first": False,
        "spo2_onset": None,
        "rr_onset": None,
        "map_onset": None,
        "temp_onset": None,
        "hr_onset": None,
        "onset_index": None,
    }
    if len(history_points) < 3:
        return profile

    baseline = history_points[0].get("values", {})
    baseline_hr = _history_value(history_points[0], "hr")
    baseline_spo2 = _history_value(history_points[0], "spo2")
    baseline_map = _history_value(history_points[0], "map")
    baseline_rr = _history_value(history_points[0], "rr")
    baseline_temp = _history_value(history_points[0], "temp")

    hr_onset = _first_metric_onset(
        history_points, metric="hr", baseline_value=baseline_hr, threshold=10, direction="rise"
    )
    spo2_onset = _first_metric_onset(
        history_points, metric="spo2", baseline_value=baseline_spo2, threshold=2, direction="drop"
    )
    map_onset = _first_metric_onset(
        history_points, metric="map", baseline_value=baseline_map, threshold=5, direction="drop"
    )
    rr_onset = _first_metric_onset(
        history_points, metric="rr", baseline_value=baseline_rr, threshold=4, direction="rise"
    )
    temp_onset = _first_metric_onset(
        history_points, metric="temp", baseline_value=baseline_temp, threshold=0.3, direction="abs"
    )

    onsets = [value for value in (hr_onset, spo2_onset, map_onset, rr_onset, temp_onset) if value is not None]
    if not onsets:
        return profile

    onset_index = min(onsets)
    total_intervals = max(1, len(history_points) - 1)
    post_onset_intervals = max(1, total_intervals - onset_index)
    onset_ratio = onset_index / total_intervals
    post_onset_ratio = post_onset_intervals / total_intervals

    profile.update(
        {
            "spo2_onset": spo2_onset,
            "rr_onset": rr_onset,
            "map_onset": map_onset,
            "temp_onset": temp_onset,
            "hr_onset": hr_onset,
            "onset_index": onset_index,
        }
    )

    profile["abrupt"] = onset_ratio >= 0.35 and post_onset_ratio <= 0.45
    profile["progressive"] = onset_ratio <= 0.35 and post_onset_ratio >= 0.5

    respiratory_candidates = [value for value in (spo2_onset, rr_onset) if value is not None]
    hemodynamic_candidates = [value for value in (map_onset, hr_onset) if value is not None]
    respiratory_first = (
        respiratory_candidates
        and (not hemodynamic_candidates or min(respiratory_candidates) <= min(hemodynamic_candidates))
    )
    hemodynamic_first = (
        hemodynamic_candidates
        and (not respiratory_candidates or min(hemodynamic_candidates) < min(respiratory_candidates))
    )
    fever_first = temp_onset is not None and (
        (not respiratory_candidates or temp_onset <= min(respiratory_candidates))
        and (not hemodynamic_candidates or temp_onset <= min(hemodynamic_candidates))
    )

    profile["respiratory_first"] = bool(respiratory_first)
    profile["hemodynamic_first"] = bool(hemodynamic_first)
    profile["fever_first"] = bool(fever_first)

    fluctuation_sign_changes = 0
    fluctuation_metrics = ("hr", "map", "rr")
    for metric in fluctuation_metrics:
        deltas: list[float] = []
        previous = _history_value(history_points[0], metric)
        for point in history_points[1:]:
            current = _history_value(point, metric, previous)
            deltas.append(current - previous)
            previous = current
        previous_sign = 0
        for delta in deltas:
            sign = 1 if delta > 0.1 else -1 if delta < -0.1 else 0
            if previous_sign and sign and sign != previous_sign:
                fluctuation_sign_changes += 1
            if sign:
                previous_sign = sign
    profile["fluctuating"] = fluctuation_sign_changes >= 3
    return profile


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
    rr_delta = _history_delta(history_points, "rr", rr)
    temporal = _temporal_profile(history_points)

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
    if (
        map_delta <= -8
        and hr_delta >= 8
        and 36.0 < temp < 38.0
        and spo2 >= 92
        and rr < 25
    ):
        add(
            "Complication cardiaque post-op possible",
            4,
            "Baisse de debit compatible avec un profil cardiaque: TAM en baisse, FC en hausse, temperature normale et atteinte respiratoire limitee.",
        )
        add(
            "Complication respiratoire post-op (pneumopathie / IRA)",
            0,
            "Atteinte respiratoire peu marquee face a une hypotension et une temperature normale.",
            against=True,
        )
        add(
            "Sepsis / complication infectieuse possible",
            0,
            "Absence de syndrome febrile net malgre une hemodynamique alteree.",
            against=True,
        )
    if shock_index >= 0.9 and map_value < 70 and 36.0 < temp < 38.0 and spo2 >= 92:
        add(
            "Complication cardiaque post-op possible",
            3,
            f"Shock index {shock_index:.2f} et TAM basse avec temperature normale, compatible avec un bas debit cardiaque.",
        )
    if spo2_delta <= -2 and spo2_delta > -5 and map_delta <= -8 and 36.0 < temp < 38.0:
        add(
            "Complication cardiaque post-op possible",
            2,
            "Baisse moderee de l'oxygenation associee a une degradation hemodynamique sans fievre franche.",
        )
    if rr_delta >= 6 and spo2_delta <= -4:
        add(
            "Complication cardiaque post-op possible",
            0,
            "Polypnee et desaturation plus marquees orientent d'abord vers un mecanisme respiratoire.",
            against=True,
        )
    if spo2 < 90 and rr >= 25:
        add(
            "Complication cardiaque post-op possible",
            0,
            "Desaturation severe avec FR haute, pattern plus compatible avec une complication respiratoire ou embolique.",
            against=True,
        )

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

    if temporal["progressive"]:
        add(
            "Sepsis / complication infectieuse possible",
            2,
            "Evolution progressive sur plusieurs etapes, compatible avec une complication infectieuse.",
        )
        add(
            "Hemorragie / hypovolemie possible",
            1,
            "Degradation progressive compatible avec une hemorragie lente.",
        )
        if rr_delta >= 4 or spo2_delta <= -2 or temp >= 38.0:
            add(
                "Complication respiratoire post-op (pneumopathie / IRA)",
                1,
                "Derive respiratoire progressive compatible avec une complication respiratoire infectieuse.",
            )
    if temporal["abrupt"]:
        add(
            "Hemorragie / hypovolemie possible",
            2,
            "Bascule rapide compatible avec une decompensation hemorragique.",
        )
        if temporal["respiratory_first"] and temp < 38.0 and (spo2 < 92 or rr >= 24 or shock_index >= 0.9):
            add(
                "Embolie pulmonaire possible",
                4,
                "Installation brutale a dominante respiratoire, compatible avec un evenement embolique.",
            )
        add(
            "Complication respiratoire post-op (pneumopathie / IRA)",
            0,
            "Evolution trop brutale pour une pneumopathie progressive typique.",
            against=True,
        )
    if temporal["respiratory_first"]:
        if temp >= 38.0 or temp_delta >= 0.5 or temporal["progressive"]:
            add(
                "Complication respiratoire post-op (pneumopathie / IRA)",
                2,
                "Les anomalies respiratoires apparaissent avant le retentissement hemodynamique, avec un contexte infectieux ou progressif.",
            )
        if temp < 38.0 and temporal["abrupt"]:
            add(
                "Embolie pulmonaire possible",
                2,
                "Le signal respiratoire apparait precocement avec une installation brutale.",
            )
    if temporal["fever_first"]:
        add(
            "Sepsis / complication infectieuse possible",
            3,
            "La temperature se modifie precocement, en faveur d'une complication infectieuse.",
        )
        add(
            "Complication respiratoire post-op (pneumopathie / IRA)",
            2,
            "La temperature augmente avant la degradation hemodynamique, compatible avec une pneumopathie.",
        )
        add(
            "Embolie pulmonaire possible",
            0,
            "Une temperature qui derive precocement oriente moins vers une embolie pulmonaire isolee.",
            against=True,
        )
        add(
            "Complication cardiaque post-op possible",
            0,
            "Une derive thermique precoce est peu compatible avec une complication cardiaque isolee.",
            against=True,
        )
        add(
            "Hemorragie / hypovolemie possible",
            0,
            "Une temperature anormale precoce est peu compatible avec une hemorragie isolee.",
            against=True,
        )
    if temporal["hemodynamic_first"]:
        add(
            "Hemorragie / hypovolemie possible",
            2,
            "Le retentissement hemodynamique precede les anomalies respiratoires.",
        )
        add(
            "Complication cardiaque post-op possible",
            2,
            "Le retentissement hemodynamique apparait en premier, compatible avec un bas debit.",
        )
        add(
            "Sepsis / complication infectieuse possible",
            0,
            "Une hemodynamique qui se degrade avant la temperature est moins en faveur d'un sepsis typique.",
            against=True,
        )
    if temporal["fluctuating"]:
        if 36.0 < temp < 38.0 and spo2 >= 95 and map_value >= 85 and rr < 24:
            add(
                "Douleur post-op non controlee possible",
                4,
                "Profil fluctuant des constantes avec oxygénation et hemodynamique preservees, compatible avec une douleur variant avec l'activite.",
            )
            add(
                "Complication respiratoire post-op (pneumopathie / IRA)",
                0,
                "Le profil fluctuant avec oxygenation preservee est moins compatible avec une complication respiratoire progressive.",
                against=True,
            )
            add(
                "Sepsis / complication infectieuse possible",
                0,
                "Le profil fluctuant sans syndrome febrile ni hypotension est peu compatible avec un sepsis evolutif.",
                against=True,
            )

    if temp >= 38.0 and temporal["progressive"] and temporal["respiratory_first"]:
        add(
            "Complication respiratoire post-op (pneumopathie / IRA)",
            3,
            "Desaturation progressive avec fievre et polypnee, profil respiratoire infectieux plausible.",
        )
        add(
            "Embolie pulmonaire possible",
            0,
            "La progression et la fievre rendent une EP isolee moins specifique.",
            against=True,
        )
    if temp >= 38.0 and temporal["progressive"] and (temporal["fever_first"] or map_delta <= -5 or map_value < 75):
        add(
            "Sepsis / complication infectieuse possible",
            4,
            "Association fievre progressive et retentissement hemodynamique, en faveur d'un sepsis.",
        )
        add(
            "Complication respiratoire post-op (pneumopathie / IRA)",
            0,
            "Le retentissement hemodynamique progressif avec fievre importante depasse une simple complication respiratoire localisee.",
            against=True,
        )

    if map_value < 70 and shock_index >= 0.9 and spo2 >= 95 and 36.0 < temp < 38.0:
        add(
            "Hemorragie / hypovolemie possible",
            3,
            "Hypoperfusion avec oxygenation preservee et temperature normale, profil compatible avec une hypovolemie.",
        )
        add(
            "Complication cardiaque post-op possible",
            0,
            "Oxygenation preservee et absence de retentissement respiratoire limitent l'argument cardiaque.",
            against=True,
        )
    if temporal["abrupt"] and temporal["hemodynamic_first"] and shock_index >= 1.0 and spo2 >= 95 and temp < 38.0:
        add(
            "Hemorragie / hypovolemie possible",
            4,
            "Bascule hemodynamique brutale avec oxygenation preservee, en faveur d'une hypovolemie aigue.",
        )
        add(
            "Complication cardiaque post-op possible",
            0,
            "Une bascule hypovolemique brutale avec SpO2 preservee est moins specifique d'un profil cardiaque.",
            against=True,
        )
    if hr_delta >= 25 and map_delta <= -20 and spo2 >= 95 and rr <= 24 and temp < 38.0:
        add(
            "Hemorragie / hypovolemie possible",
            4,
            "Association forte FC en hausse, TAM en chute et oxygenation preservee compatible avec une hemorragie.",
        )
        add(
            "Complication cardiaque post-op possible",
            0,
            "L'absence d'atteinte respiratoire significative diminue la probabilite d'une complication cardiaque.",
            against=True,
        )

    if map_value < 75 and shock_index >= 0.9 and 90 <= spo2 < 95 and rr < 25 and 36.0 < temp < 38.0:
        add(
            "Complication cardiaque post-op possible",
            4,
            "Bas debit avec desaturation moderee et polypnee limitee, compatible avec une origine cardiaque.",
        )
        add(
            "Hemorragie / hypovolemie possible",
            0,
            "Une desaturation associee a un bas debit rend l'hypovolemie pure moins specifique.",
            against=True,
        )
        add(
            "Embolie pulmonaire possible",
            0,
            "Le retentissement respiratoire reste modere et l'hemodynamique se degrade d'abord, ce qui est moins specifique d'une EP.",
            against=True,
        )
    if temporal["abrupt"] and temporal["hemodynamic_first"] and 90 <= spo2 < 95 and rr < 25 and 36.0 < temp < 38.0:
        add(
            "Complication cardiaque post-op possible",
            4,
            "Bascule brutale a dominante hemodynamique avec atteinte respiratoire moderee et temperature normale, compatible avec une decompensation cardiaque.",
        )
        add(
            "Embolie pulmonaire possible",
            0,
            "La polypnee et la desaturation ne sont pas au premier plan malgre une bascule brutale.",
            against=True,
        )

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
