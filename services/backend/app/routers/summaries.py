from __future__ import annotations

from fastapi import APIRouter, Request

from app.llm.clinical_context import ClinicalContextPayload
from app.routers.llm import resolve_patient_analysis


router = APIRouter(prefix="/api/summaries", tags=["summaries"])


@router.get("/{patient_id}")
async def patient_summary(patient_id: str, request: Request):
    return await _patient_summary_with_context(
        patient_id,
        request,
        ClinicalContextPayload(),
        force=False,
    )


@router.post("/{patient_id}/analyze")
async def patient_summary_with_context(
    patient_id: str,
    payload: ClinicalContextPayload,
    request: Request,
):
    return await _patient_summary_with_context(
        patient_id,
        request,
        payload,
        force=True,
    )


async def _patient_summary_with_context(
    patient_id: str,
    request: Request,
    payload: ClinicalContextPayload,
    *,
    force: bool,
):
    analysis = await resolve_patient_analysis(patient_id, request, payload, force=force)
    return {
        "patient_id": patient_id,
        "source": analysis.source,
        "llm_status": analysis.llm_status,
        "summary": analysis.summary_text,
        "clinical_context": payload.as_prompt_dict(),
        "analysis_state": analysis.analysis_state.model_dump(),
    }
