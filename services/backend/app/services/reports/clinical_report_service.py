from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import Request

from app.llm.clinical_context import ClinicalContextPayload, QuestionnaireAnswerPayload, QuestionnaireResponsePayload


TERRAIN_GUIDANCE_RULES = [
    {
        "keywords": ("bpco", "asthme", "saos", "obesite", "tabag", "fumeur", "thorac"),
        "title": "Reserve respiratoire",
        "surveillance": "Surveiller de facon rapprochee SpO2, FR, dyspnee, vigilance et tolerance a la mobilisation.",
        "prudence": "Rester prudent avec opioides et sedatifs; toute dyspnee nouvelle doit faire reevaluer un foyer respiratoire, une EP ou une complication cardiaque.",
    },
    {
        "keywords": ("anemie", "anticoag", "antiagre", "hemorrag", "transfusion"),
        "title": "Terrain hemorragique",
        "surveillance": "Verifier pansement, pertes visibles, paleur, malaise, FC, PA/TAM et douleur inhabituelle.",
        "prudence": "Une tachycardie isolee ou une hypotension moderee ne doivent pas etre banalisees sur ce terrain.",
    },
    {
        "keywords": ("tvp", "ep", "cancer", "arthroplastie", "immobil", "obesite"),
        "title": "Terrain thromboembolique",
        "surveillance": "Rechercher dyspnee brutale, douleur thoracique pleurale, douleur de mollet, oedeme asymetrique et malaise.",
        "prudence": "Garder un seuil bas de reevaluation si des symptomes emboliques apparaissent ou se majorent.",
    },
    {
        "keywords": ("diab", "immun", "cortico", "infection", "renal", "cirrh", "hepato"),
        "title": "Terrain infectieux / metabolique",
        "surveillance": "Surveiller temperature, plaie, signes urinaires, douleur abdominale, hydratation et comportement.",
        "prudence": "Chez un patient fragile ou diabetique, une derive lente des constantes doit faire reevaluer plus tot un foyer infectieux ou un sepsis debutant.",
    },
    {
        "keywords": ("coronar", "cardiaque", "insuffisance cardiaque", "fragil", "delir", "age"),
        "title": "Terrain cardio-frailty",
        "surveillance": "Rechercher dyspnee, hypotension, signes de bas debit, confusion, baisse fonctionnelle et mauvaise tolerance a la mobilisation.",
        "prudence": "Ne pas opposer trop vite etiologie cardiaque, hemorragique et infectieuse si l'hemodynamique se degrade.",
    },
    {
        "keywords": ("douleur", "opio", "anxiet"),
        "title": "Douleur / opioides",
        "surveillance": "Documenter douleur au repos, a la mobilisation, sedation, FR et SpO2 si analgesiants opioides.",
        "prudence": "Une douleur importante associee a hypoxemie, hypotension, fievre ou saignement ne doit pas etre attribuee a une douleur simple.",
    },
]


TERRAIN_GUIDANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "immediate_actions": {"type": "array", "items": {"type": "string"}},
        "surveillance_points": {"type": "array", "items": {"type": "string"}},
        "escalation_triggers": {"type": "array", "items": {"type": "string"}},
        "transmission_summary": {"type": "string"},
        "cited_sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "immediate_actions",
        "surveillance_points",
        "escalation_triggers",
        "transmission_summary",
        "cited_sources",
    ],
}


class AnalysisResolver(Protocol):
    async def __call__(
        self,
        patient_id: str,
        request: Request,
        payload: ClinicalContextPayload,
        *,
        force: bool = False,
        persist_cache: bool = True,
    ) -> Any: ...


async def build_clinical_report_payload(
    patient_id: str,
    request: Request,
    *,
    analysis_resolver: AnalysisResolver,
    analysis_cache_type: str,
) -> dict[str, Any] | None:
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        return None

    last_vitals = services.last_vitals.get(patient_id)
    if not last_vitals:
        return None

    current_vitals = _coerce_current_vitals(last_vitals)
    history_points = services.influx.query_history(patient_id=patient_id, metric="all", hours=0)
    alerts = services.postgres.list_alerts(patient_id=patient_id, limit=8)
    baseline_values, baseline_timestamp = _baseline_snapshot(
        history_points,
        current_vitals,
        fallback_timestamp=str(last_vitals.get("ts") or ""),
    )
    scenario_label = (
        last_vitals.get("scenario_label")
        or last_vitals.get("scenario")
        or patient.get("scenario")
        or "Cas clinique non renseigne"
    )

    baseline_analysis = await analysis_resolver(
        patient_id,
        request,
        ClinicalContextPayload(),
        force=True,
        persist_cache=False,
    )

    cache_row = services.postgres.get_analysis_cache(patient_id, analysis_cache_type)
    questionnaire_payload = _questionnaire_payload_from_cache(cache_row.get("questionnaire") if cache_row else None)
    adjusted_analysis = None
    questionnaire_details = None
    questionnaire_selection = None

    if getattr(services, "questionnaire_engine", None):
        questionnaire_selection = services.questionnaire_engine.select_modules(
            last_vitals=last_vitals,
            alerts=alerts,
            history_points=history_points,
        )

    if questionnaire_payload and getattr(services, "questionnaire_engine", None):
        raw_answers = [answer.model_dump() for answer in questionnaire_payload.answers]
        questionnaire_details = services.questionnaire_engine.enrich_answers(
            raw_answers,
            responder=questionnaire_payload.responder,
            comment=questionnaire_payload.comment,
        )
        adjusted_analysis = await analysis_resolver(
            patient_id,
            request,
            ClinicalContextPayload(questionnaire=questionnaire_payload),
            force=True,
            persist_cache=False,
        )

    final_analysis = adjusted_analysis or baseline_analysis
    leading_hypothesis = _leading_hypothesis(final_analysis)
    surgery_type = str(last_vitals.get("surgery_type") or patient.get("surgery_type") or "")
    terrain_guidance = _terrain_guidance(
        history=patient.get("history", []),
        surgery_type=surgery_type,
        leading_hypothesis=leading_hypothesis,
    )
    terrain_guidance_llm = await _build_terrain_guidance_for_report(
        services=services,
        patient_id=patient_id,
        surgery_type=surgery_type,
        scenario_label=scenario_label,
        last_vitals=current_vitals,
        alerts=alerts,
        patient_history=patient.get("history", []),
        leading_hypothesis=leading_hypothesis,
    )

    return {
        "patient": patient,
        "patient_id": patient_id,
        "scenario_label": scenario_label,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "last_vitals": current_vitals,
        "last_vitals_timestamp": str(last_vitals.get("ts") or ""),
        "baseline_values": baseline_values,
        "baseline_timestamp": baseline_timestamp,
        "alerts": alerts,
        "baseline_analysis": baseline_analysis,
        "adjusted_analysis": adjusted_analysis,
        "final_analysis": final_analysis,
        "questionnaire_details": questionnaire_details,
        "questionnaire_selection": questionnaire_selection,
        "terrain_guidance": terrain_guidance,
        "terrain_guidance_llm": terrain_guidance_llm,
        "leading_hypothesis": leading_hypothesis,
        "contingency_points": _build_contingency_points(
            last_vitals=current_vitals,
            leading_hypothesis=leading_hypothesis,
        ),
    }


async def _build_terrain_guidance_for_report(
    *,
    services: Any,
    patient_id: str,
    surgery_type: str,
    scenario_label: str,
    last_vitals: dict[str, Any],
    alerts: list[dict[str, Any]],
    patient_history: list[str],
    leading_hypothesis: str,
) -> dict[str, Any]:
    feedback_rows = services.postgres.list_ml_feedback(patient_id=patient_id, limit=20)
    diagnosis_feedback = next(
        (
            row
            for row in feedback_rows
            if row.get("diagnosis_decision") in {"validated", "rejected"}
            and str(row.get("final_diagnosis") or "").strip()
        ),
        None,
    )
    if not diagnosis_feedback:
        return {
            "available": False,
            "warning": "Validation medecin de la pathologie requise avant conduite a tenir retravaillee.",
            "source": "rule-based",
            "llm_status": "rule-based",
            "personalization_level": "low",
            "diagnosis_decision": "pending",
            "diagnosis_final": "",
            "immediate_actions": [],
            "surveillance_points": [],
            "escalation_triggers": [],
            "transmission_summary": "",
            "cited_sources": [],
        }

    diagnosis_decision = str(diagnosis_feedback.get("diagnosis_decision") or "validated")
    diagnosis_final = str(diagnosis_feedback.get("final_diagnosis") or "").strip()
    context_count = len(patient_history)
    personalization_level = "low" if context_count == 0 else ("medium" if context_count <= 3 else "high")
    warning = "" if context_count > 0 else "Aucun antecedent renseigne: conduite plus generaliste et moins precise."

    current_map = int(round(float(last_vitals.get("map", 0) or 0)))
    current_spo2 = int(round(float(last_vitals.get("spo2", 0) or 0)))
    current_rr = int(round(float(last_vitals.get("rr", 0) or 0)))
    current_temp = round(float(last_vitals.get("temp", 0) or 0), 1)
    alert_titles = [str(alert.get("title") or "") for alert in alerts[:3] if str(alert.get("title") or "").strip()]
    kb_guidance = services.knowledge_base.get_excerpt("terrain_guidance") or "source non disponible"
    kb_sources = services.knowledge_base.get_excerpt("terrain_sources") or "source non disponible"

    prompt = (
        "Produis une conduite a tenir post-operatoire prudente, en JSON strict.\n"
        "N'utilise que les donnees valides ci-dessous.\n"
        f"Decision medecin: {diagnosis_decision}; diagnostic final: {diagnosis_final}.\n"
        f"Patient {patient_id}, chirurgie: {surgery_type}, scenario: {scenario_label}.\n"
        f"Constantes: SpO2 {current_spo2}%, TAM {current_map} mmHg, FR {current_rr}/min, T {current_temp}C.\n"
        f"Alertes recentes: {', '.join(alert_titles) if alert_titles else 'aucune'}.\n"
        f"Antecedents connus: {', '.join(patient_history) if patient_history else 'aucun'}.\n"
        f"Hypothese dominante courante: {leading_hypothesis}.\n"
        f"Niveau de personnalisation attendu: {personalization_level}.\n"
        f"KB guidance:\n{kb_guidance}\n"
        f"KB sources:\n{kb_sources}\n"
    )
    structured = await services.llm_client.generate_structured(
        prompt,
        TERRAIN_GUIDANCE_SCHEMA,
        system=(
            "Assistant clinique prudent. N'emets pas de diagnostic certain. "
            "Retourne uniquement un JSON conforme avec sources citees."
        ),
    )

    source = "ollama"
    llm_status = "ollama"
    if not isinstance(structured, dict):
        source = "rule-based"
        llm_status = "llm-unavailable" if services.settings.enable_llm else "disabled"
        structured = {
            "immediate_actions": [
                "Reevaluer les constantes et le statut clinique rapidement.",
                "Tracer la decision medicale et le diagnostic final dans la transmission.",
            ],
            "surveillance_points": [
                "Surveiller SpO2, FR, TAM, FC, temperature et signes fonctionnels.",
                "Rechercher une derive par rapport aux alertes et mesures recentes.",
            ],
            "escalation_triggers": [
                "Escalade immediate si deterioration brutale ou mal toleree.",
                "Escalade si aggravation persistante malgre surveillance rapprochee.",
            ],
            "transmission_summary": f"Diagnostic final medical: {diagnosis_final}.",
            "cited_sources": ["kb/postop-terrain-context-guidance.md", "kb/postop-terrain-context-sources.md"],
        }

    def _clean_lines(value: object, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback

    return {
        "available": True,
        "warning": warning,
        "source": source,
        "llm_status": llm_status,
        "personalization_level": personalization_level,
        "diagnosis_decision": diagnosis_decision,
        "diagnosis_final": diagnosis_final,
        "immediate_actions": _clean_lines(
            structured.get("immediate_actions"),
            ["Poursuivre une surveillance clinique rapprochee."],
        )[:6],
        "surveillance_points": _clean_lines(
            structured.get("surveillance_points"),
            ["Recontroler constantes et signes fonctionnels a intervalle rapproche."],
        )[:6],
        "escalation_triggers": _clean_lines(
            structured.get("escalation_triggers"),
            ["Escalade immediate en cas de deterioration clinique."],
        )[:6],
        "transmission_summary": str(structured.get("transmission_summary") or "").strip()
        or f"Diagnostic final medical: {diagnosis_final}.",
        "cited_sources": _clean_lines(
            structured.get("cited_sources"),
            ["kb/postop-terrain-context-guidance.md", "kb/postop-terrain-context-sources.md"],
        )[:6],
    }


def _baseline_snapshot(
    history_points: list[dict[str, Any]],
    current_vitals: dict[str, Any],
    *,
    fallback_timestamp: str,
) -> tuple[dict[str, float], str]:
    if history_points:
        start = history_points[0]
        values = dict(start.get("values", {}))
        if "shock_index" not in values:
            sbp = float(values.get("sbp", 0) or 0)
            hr = float(values.get("hr", 0) or 0)
            values["shock_index"] = round(hr / sbp, 2) if sbp else 0.0
        return _coerce_current_vitals(values), str(start.get("ts") or "")
    return current_vitals, fallback_timestamp


def _coerce_current_vitals(values: dict[str, Any]) -> dict[str, Any]:
    sbp = float(values.get("sbp", 0) or 0)
    hr = float(values.get("hr", 0) or 0)
    return {
        "hr": float(values.get("hr", 0) or 0),
        "spo2": float(values.get("spo2", 0) or 0),
        "sbp": sbp,
        "dbp": float(values.get("dbp", 0) or 0),
        "map": float(values.get("map", 0) or 0),
        "rr": float(values.get("rr", 0) or 0),
        "temp": float(values.get("temp", 0) or 0),
        "shock_index": float(values.get("shock_index", round(hr / sbp, 2) if sbp else 0) or 0),
        "postop_day": values.get("postop_day", 0),
        "room": values.get("room", ""),
        "surgery_type": values.get("surgery_type", ""),
    }


def _questionnaire_payload_from_cache(raw: Any) -> QuestionnaireResponsePayload | None:
    if not isinstance(raw, dict):
        return None
    responder = str(raw.get("responder") or "patient").strip() or "patient"
    comment = str(raw.get("comment") or "").strip()
    answers: list[QuestionnaireAnswerPayload] = []
    for answer in raw.get("answers") or []:
        if not isinstance(answer, dict):
            continue
        module_id = str(answer.get("module_id") or "").strip()
        question_id = str(answer.get("question_id") or "").strip()
        value = str(answer.get("answer") or "").strip()
        if not module_id or not question_id or not value:
            continue
        answers.append(
            QuestionnaireAnswerPayload(
                module_id=module_id,
                question_id=question_id,
                answer=value,
            )
        )
    if not answers and not comment and responder == "patient":
        return None
    return QuestionnaireResponsePayload(responder=responder, comment=comment, answers=answers)


def _leading_hypothesis(analysis: Any) -> str:
    ranking = getattr(analysis, "hypothesis_ranking", []) or []
    if not ranking:
        return "Hypothese non renseignee"
    return str(ranking[0].label)


def _terrain_guidance(*, history: list[str], surgery_type: str, leading_hypothesis: str) -> list[dict[str, str]]:
    blob = " ".join([*history, surgery_type, leading_hypothesis]).lower()
    guidance: list[dict[str, str]] = []
    for rule in TERRAIN_GUIDANCE_RULES:
        if any(keyword in blob for keyword in rule["keywords"]):
            guidance.append(
                {
                    "title": str(rule["title"]),
                    "surveillance": str(rule["surveillance"]),
                    "prudence": str(rule["prudence"]),
                }
            )
    if not guidance:
        guidance.append(
            {
                "title": "Surveillance transversale",
                "surveillance": "Suivre l'evolution des constantes, les signes fonctionnels et les alertes recentes.",
                "prudence": "Si plusieurs signaux se cumulent ou si un symptome est brutal ou mal tolere, accelerer la reevaluation.",
            }
        )
    return guidance[:4]


def _build_contingency_points(*, last_vitals: dict[str, Any], leading_hypothesis: str) -> list[str]:
    leading = leading_hypothesis.lower()
    points: list[str] = []

    if last_vitals.get("spo2", 0) < 94 or "respiratoire" in leading or "embolie" in leading:
        points.append("Escalade rapide si dyspnee nouvelle, douleur thoracique, hemoptysie ou desaturation.")
    if last_vitals.get("map", 0) < 70 or last_vitals.get("shock_index", 0) >= 0.9 or "hemorragie" in leading or "cardiaque" in leading:
        points.append("Escalade rapide si hypotension, tachycardie, malaise, syncope ou saignement visible.")
    if last_vitals.get("temp", 0) >= 38.0 or last_vitals.get("temp", 0) <= 36.0 or "infect" in leading or "sepsis" in leading:
        points.append("Reevaluation rapide si fievre ou frissons, rougeur de plaie, ecoulement, douleur abdominale inhabituelle ou signes urinaires.")
    if "douleur" in leading:
        points.append("Ne pas conclure a une douleur simple si elle s'associe a hypoxemie, hypotension, fievre ou saignement.")
    if not points:
        points.append("Reevaluer rapidement tout symptome brutal, mal tolere ou tout cumul d'alertes recentes.")
    return points[:4]
