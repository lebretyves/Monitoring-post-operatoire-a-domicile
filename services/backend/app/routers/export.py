from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from app.routers.llm import ANALYSIS_CACHE_TYPE, resolve_patient_analysis
from app.services.reports.clinical_report_service import build_clinical_report_payload
from app.services.reports.pdf_renderer import render_clinical_report_pdf


router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/{patient_id}/csv")
def export_csv(patient_id: str, request: Request, hours: int = 24):
    points = request.app.state.services.influx.query_history(patient_id=patient_id, metric="all", hours=hours)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ts", "hr", "spo2", "sbp", "dbp", "map", "rr", "temp", "shock_index"])
    for point in points:
        values = point.get("values", {})
        writer.writerow(
            [
                point["ts"],
                values.get("hr", ""),
                values.get("spo2", ""),
                values.get("sbp", ""),
                values.get("dbp", ""),
                int(round(float(values.get("map", 0)))) if values.get("map", "") != "" else "",
                values.get("rr", ""),
                values.get("temp", ""),
                values.get("shock_index", ""),
            ]
        )
    content = io.BytesIO(buffer.getvalue().encode("utf-8"))
    return StreamingResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{patient_id}-vitals.csv"'},
    )


@router.get("/{patient_id}/pdf")
async def export_pdf(patient_id: str, request: Request):
    report_payload = await build_clinical_report_payload(
        patient_id,
        request,
        analysis_resolver=resolve_patient_analysis,
        analysis_cache_type=ANALYSIS_CACHE_TYPE,
    )
    if not report_payload:
        return Response(status_code=404)

    pdf_bytes = render_clinical_report_pdf(report_payload)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{patient_id}-report.pdf"'},
    )
