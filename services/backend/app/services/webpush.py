from __future__ import annotations

import asyncio
import base64
import json
import logging
import tempfile
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush


logger = logging.getLogger(__name__)


class WebPushService:
    def __init__(self, settings, postgres) -> None:
        self.settings = settings
        self.postgres = postgres
        self._vapid_key_file_path: str | None = None

    @property
    def _vapid_private_key_pem(self) -> str:
        raw_key = self.settings.vapid_private_key.replace("\\n", "\n").strip()
        if "BEGIN" in raw_key:
            return raw_key

        # Accept web-push style base64url private keys and convert to PEM for pywebpush.
        padding = "=" * ((4 - (len(raw_key) % 4)) % 4)
        key_bytes = base64.urlsafe_b64decode(raw_key + padding)
        if len(key_bytes) != 32:
            raise ValueError("Invalid VAPID private key size; expected 32-byte base64url or PEM key")
        private_value = int.from_bytes(key_bytes, "big")
        private_key = ec.derive_private_key(private_value, ec.SECP256R1())
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return pem.decode("utf-8")

    @property
    def _vapid_private_key_path(self) -> str:
        if self._vapid_key_file_path:
            return self._vapid_key_file_path
        tmp = tempfile.NamedTemporaryFile(prefix="postop-vapid-", suffix=".pem", delete=False)
        tmp.write(self._vapid_private_key_pem.encode("utf-8"))
        tmp.flush()
        tmp.close()
        self._vapid_key_file_path = tmp.name
        return self._vapid_key_file_path

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.enable_webpush
            and self.settings.vapid_public_key
            and self.settings.vapid_private_key
        )

    async def dispatch_notification(self, notification: dict[str, Any], user_id: str | None = None) -> None:
        if not self.enabled:
            return
        payload = {
            "title": notification.get("title", "Alerte monitorage"),
            "body": f"{notification.get('patient_id', '')} - {notification.get('message', '')}",
            "patient_id": notification.get("patient_id"),
            "notification_id": notification.get("id"),
            "level": notification.get("level"),
        }
        subscriptions = self.postgres.list_active_push_subscriptions(user_id=user_id)
        if not subscriptions:
            return
        await asyncio.to_thread(self._send_to_subscriptions, subscriptions, payload)

    def _send_to_subscriptions(self, subscriptions: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        for sub in subscriptions:
            subscription_info = {
                "endpoint": sub["endpoint"],
                "keys": {
                    "p256dh": sub["p256dh"],
                    "auth": sub["auth"],
                },
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps(payload),
                    vapid_private_key=self._vapid_private_key_path,
                    vapid_claims={"sub": self.settings.vapid_claims_sub},
                    ttl=60,
                )
            except WebPushException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                logger.warning("Web push delivery failed status=%s endpoint=%s", status_code, sub.get("endpoint"))
                if status_code in {404, 410}:
                    self.postgres.deactivate_push_subscription(sub["endpoint"])
            except Exception:
                logger.exception("Unexpected error while delivering web push")
