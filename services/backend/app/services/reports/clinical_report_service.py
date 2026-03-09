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
    terrain_guidance = _terrain_guidance(
        history=patient.get("history", []),
        surgery_type=str(last_vitals.get("surgery_type") or patient.get("surgery_type") or ""),
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
        "leading_hypothesis": leading_hypothesis,
        "contingency_points": _build_contingency_points(
            last_vitals=current_vitals,
            leading_hypothesis=leading_hypothesis,
        ),
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
