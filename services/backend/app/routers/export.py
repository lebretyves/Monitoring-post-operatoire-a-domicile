from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, StreamingResponse


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
def export_pdf(patient_id: str):
    return PlainTextResponse(
        f"PDF export placeholder for {patient_id}. CSV export already works in this scaffold."
    )
