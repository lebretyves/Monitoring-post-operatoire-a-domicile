from __future__ import annotations

from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("/{patient_id}")
def trend_history(patient_id: str, request: Request, metric: str = "all", hours: int = 24):
    services = request.app.state.services
    points = services.influx.query_history(patient_id=patient_id, metric=metric, hours=hours)
    return {
        "patient_id": patient_id,
        "metric": metric,
        "hours": hours,
        "points": points,
        "anomaly": services.anomaly_service.score(points),
    }
