from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.llm.prompt_templates import SUMMARY_SYSTEM_PROMPT, build_summary_prompt


router = APIRouter(prefix="/api/summaries", tags=["summaries"])


@router.get("/{patient_id}")
async def patient_summary(patient_id: str, request: Request):
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    last_vitals = services.last_vitals.get(patient_id)
    if not last_vitals:
        raise HTTPException(status_code=404, detail="No vitals yet")
    pathology = last_vitals.get("scenario_label") or last_vitals.get("scenario")
    surgery_type = last_vitals.get("surgery_type", patient["surgery_type"])
    alerts = services.postgres.list_alerts(
        patient_id=patient_id,
        pathology=pathology,
        surgery_type=surgery_type,
        limit=5,
    )
    prompt = build_summary_prompt(patient, last_vitals, alerts)
    summary = await services.llm_client.summarize(prompt, system=SUMMARY_SYSTEM_PROMPT)
    source = "ollama"
    if not summary:
        source = "rule-based"
        summary = (
            f"{patient['id']} est en suivi post-op apres {patient['surgery_type']} au jour "
            f"{patient['postop_day']}. Dernieres constantes: FC {last_vitals['hr']} bpm, SpO2 {last_vitals['spo2']}%, "
            f"TAM {int(round(last_vitals['map']))}, FR {last_vitals['rr']}/min, T\u00B0C {last_vitals['temp']} \u00B0C. "
            f"{len(alerts)} alertes recentes."
        )
    services.postgres.store_note(patient_id=patient_id, content=summary, source=source)
    return {"patient_id": patient_id, "source": source, "summary": summary}
