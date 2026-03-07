from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.ws.events import ack_event


router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    request: Request,
    patient_id: str | None = None,
    pathology: str | None = None,
    surgery_type: str | None = None,
    limit: int = 100,
):
    return request.app.state.services.postgres.list_alerts(
        patient_id=patient_id,
        pathology=pathology,
        surgery_type=surgery_type,
        limit=limit,
    )


@router.post("/{alert_id}/ack")
async def ack_alert(alert_id: int, request: Request, user: str = "demo"):
    services = request.app.state.services
    alert = services.postgres.ack_alert(alert_id, user)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await services.ws_manager.broadcast(ack_event(alert))
    return alert
