from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse


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
def export_pdf(patient_id: str, request: Request):
    services = request.app.state.services
    patient = services.postgres.get_patient(patient_id)
    if not patient:
        return Response(status_code=404)

    last_vitals = services.last_vitals.get(patient_id) or {}
    alerts = services.postgres.list_alerts(patient_id=patient_id, limit=6)
    lines = [
        "Monitoring post-operatoire a domicile",
        "",
        f"Patient: {patient_id}",
        f"Chirurgie: {patient.get('surgery_type', 'non renseignee')}",
        f"Jour post-op: J{patient.get('postop_day', 'N/A')}",
        f"Export: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        "",
        "Dernieres constantes",
        f"- FC: {last_vitals.get('hr', 'N/A')} bpm",
        f"- SpO2: {last_vitals.get('spo2', 'N/A')} %",
        f"- TA: {last_vitals.get('sbp', 'N/A')}/{last_vitals.get('dbp', 'N/A')} mmHg",
        f"- TAM: {int(round(float(last_vitals.get('map', 0)))) if last_vitals else 'N/A'} mmHg",
        f"- FR: {last_vitals.get('rr', 'N/A')} /min",
        f"- T C: {last_vitals.get('temp', 'N/A')} C",
        "",
        "Alertes recentes",
    ]

    if alerts:
        for alert in alerts:
            historical = "historique" if alert.get("metric_snapshot", {}).get("historical_backfill") else "active"
            lines.extend(
                [
                    f"- [{alert.get('level', 'N/A')}] {alert.get('title', 'Alerte')}",
                    f"  {alert.get('message', '')}",
                    f"  Statut: {alert.get('status', 'OPEN')} | Nature: {historical} | Date: {alert.get('created_at', '')}",
                ]
            )
    else:
        lines.append("- Aucune alerte recente.")

    pdf_bytes = _build_simple_pdf(lines)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{patient_id}-report.pdf"'},
    )


def _build_simple_pdf(lines: list[str]) -> bytes:
    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(_wrap_line(line, width=90))

    y_position = 780
    content_lines = ["BT", "/F1 11 Tf", "50 810 Td", "14 TL"]
    first_line = True
    for line in wrapped_lines:
        escaped = (
            line.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        if first_line:
            content_lines.append(f"({escaped}) Tj")
            first_line = False
        else:
            content_lines.append("T*")
            content_lines.append(f"({escaped}) Tj")
        y_position -= 14
        if y_position < 60:
            break
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
        f"4 0 obj << /Length {len(content_stream)} >> stream\n".encode("latin-1") + content_stream + b"\nendstream endobj",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)
        output.extend(b"\n")
    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("latin-1")
    )
    return bytes(output)


def _wrap_line(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or [text]
