from __future__ import annotations

from typing import Any

from sklearn.ensemble import IsolationForest

from app.ml.features import build_feature_matrix


class AnomalyService:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def score(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}
        matrix = build_feature_matrix(history)
        if len(matrix) < 16:
            return {"enabled": True, "status": "not-enough-data"}
        model = IsolationForest(random_state=42, contamination=0.1)
        model.fit(matrix)
        prediction = int(model.predict([matrix[-1]])[0])
        return {"enabled": True, "status": "ok", "is_anomaly": prediction == -1}
