from __future__ import annotations

from typing import Any


def vitals_event(reading: dict[str, Any]) -> dict[str, Any]:
    return {"type": "vitals", "patient_id": reading["patient_id"], "payload": reading}


def alert_event(alert: dict[str, Any]) -> dict[str, Any]:
    return {"type": "alert", "patient_id": alert["patient_id"], "payload": alert}


def ack_event(alert: dict[str, Any]) -> dict[str, Any]:
    return {"type": "ack", "patient_id": alert["patient_id"], "payload": alert}


def notification_event(notification: dict[str, Any]) -> dict[str, Any]:
    return {"type": "notification", "patient_id": notification["patient_id"], "payload": notification}


def notification_read_event(notification: dict[str, Any]) -> dict[str, Any]:
    return {"type": "notification_read", "patient_id": notification["patient_id"], "payload": notification}


def notifications_reset_event(patient_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "notifications_reset",
        "patient_id": "*",
        "payload": {
            "patient_ids": patient_ids,
            "scope": "refresh",
        },
    }
