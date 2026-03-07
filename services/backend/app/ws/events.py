from __future__ import annotations

from typing import Any


def vitals_event(reading: dict[str, Any]) -> dict[str, Any]:
    return {"type": "vitals", "patient_id": reading["patient_id"], "payload": reading}


def alert_event(alert: dict[str, Any]) -> dict[str, Any]:
    return {"type": "alert", "patient_id": alert["patient_id"], "payload": alert}


def ack_event(alert: dict[str, Any]) -> dict[str, Any]:
    return {"type": "ack", "patient_id": alert["patient_id"], "payload": alert}
