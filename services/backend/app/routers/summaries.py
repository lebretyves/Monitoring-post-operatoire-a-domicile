from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.llm.clinical_context import ClinicalContextPayload
from app.llm.prompt_templates import SUMMARY_SYSTEM_PROMPT, build_summary_prompt


router = APIRouter(prefix="/api/summaries", tags=["summaries"])


@router.get("/{patient_id}")
async def patient_summary(patient_id: str, request: Request):
    return await _patient_summary_with_context(patient_id, request, ClinicalContextPayload())


@router.post("/{patient_id}/analyze")
async def patient_summary_with_context(
    patient_id: str,
    payload: ClinicalContextPayload,
    request: Request,
):
    return await _patient_summary_with_context(patient_id, request, payload)


async def _patient_summary_with_context(
    patient_id: str,
    request: Request,
    payload: ClinicalContextPayload,
):
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    last_vitals = services.last_vitals.get(patient_id)
    if not last_vitals:
        raise HTTPException(status_code=404, detail="No vitals yet")
    alerts = services.postgres.list_alerts(patient_id=patient_id, limit=5)
    history_points = services.influx.query_history(patient_id=patient_id, metric="all", hours=0)
    knowledge_excerpt = services.knowledge_base.get_excerpt("summary")
    prompt_context = payload.as_prompt_dict()
    questionnaire_payload = prompt_context.get("questionnaire")
    if questionnaire_payload and getattr(services, "questionnaire_engine", None):
        prompt_context["questionnaire"] = services.questionnaire_engine.enrich_answers(
            questionnaire_payload.get("answers", []),
            responder=str(questionnaire_payload.get("responder") or "patient"),
            comment=str(questionnaire_payload.get("comment") or ""),
        )
    prompt = build_summary_prompt(
        patient,
        last_vitals,
        alerts,
        history_points,
        clinical_context=prompt_context,
        knowledge_excerpt=knowledge_excerpt,
    )
    summary = await services.llm_client.summarize(prompt, system=SUMMARY_SYSTEM_PROMPT)
    source = "ollama"
    llm_status = "ollama"
    if not summary:
        source = "rule-based"
        llm_status = "llm-unavailable" if services.settings.enable_llm else "disabled"
        summary = (
            f"{patient['id']} est en suivi post-op apres {patient['surgery_type']} au jour "
            f"{patient['postop_day']}. Dernieres constantes: FC {last_vitals['hr']} bpm, SpO2 {last_vitals['spo2']}%, "
            f"TAM {int(round(last_vitals['map']))}, FR {last_vitals['rr']}/min, T\u00B0C {last_vitals['temp']} \u00B0C. "
            f"{len(alerts)} alertes recentes."
        )
    services.postgres.store_note(patient_id=patient_id, content=summary, source=source)
    return {
        "patient_id": patient_id,
        "source": source,
        "llm_status": llm_status,
        "summary": summary,
        "clinical_context": payload.as_prompt_dict(),
    }
