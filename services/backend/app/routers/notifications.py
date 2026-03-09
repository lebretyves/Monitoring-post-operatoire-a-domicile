from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.ws.events import notification_read_event


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    request: Request,
    patient_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
):
    normalized_status = status.upper() if status else None
    return request.app.state.services.postgres.list_notifications(
        patient_id=patient_id,
        status=normalized_status,
        limit=limit,
    )


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: Request, user: str = "demo"):
    services = request.app.state.services
    notification = services.postgres.mark_notification_read(notification_id, user)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    await services.ws_manager.broadcast(notification_read_event(notification))
    return notification
