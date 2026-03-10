from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/push", tags=["push"])


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscriptionPayload(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: PushSubscriptionKeys


class RegisterPushSubscriptionRequest(BaseModel):
    user_id: str = Field(default="demo", min_length=1)
    device_id: str = Field(default="web-browser", min_length=1)
    subscription: PushSubscriptionPayload
    user_agent: str | None = None


class DeletePushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=1)


@router.post("/subscriptions")
def register_push_subscription(payload: RegisterPushSubscriptionRequest, request: Request):
    row = request.app.state.services.postgres.upsert_push_subscription(
        user_id=payload.user_id,
        device_id=payload.device_id,
        endpoint=payload.subscription.endpoint,
        p256dh=payload.subscription.keys.p256dh,
        auth=payload.subscription.keys.auth,
        user_agent=payload.user_agent,
    )
    return {"status": "subscribed", "subscription": row}


@router.delete("/subscriptions")
def delete_push_subscription(payload: DeletePushSubscriptionRequest, request: Request):
    removed = request.app.state.services.postgres.deactivate_push_subscription(payload.endpoint)
    if not removed:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"status": "unsubscribed", "endpoint": payload.endpoint}


@router.get("/config")
def get_push_config(request: Request):
    settings = request.app.state.services.settings
    return {
        "enabled": settings.enable_webpush,
        "public_key": settings.vapid_public_key,
    }
