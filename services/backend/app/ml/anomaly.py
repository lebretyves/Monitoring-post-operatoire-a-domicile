from __future__ import annotations

from typing import Any

from sklearn.ensemble import IsolationForest

from app.ml.features import build_feature_matrix


class AnomalyService:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._last_signature: tuple[Any, ...] | None = None
        self._last_result: dict[str, Any] | None = None

    def score(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}
        signature = self._signature(history)
        if signature is not None and signature == self._last_signature and self._last_result is not None:
            return dict(self._last_result)
        matrix = build_feature_matrix(history)
        if len(matrix) < 16:
            result = {"enabled": True, "status": "not-enough-data"}
            self._last_signature = signature
            self._last_result = dict(result)
            return result
        model = IsolationForest(random_state=42, contamination=0.1)
        model.fit(matrix)
        prediction = int(model.predict([matrix[-1]])[0])
        result = {"enabled": True, "status": "ok", "is_anomaly": prediction == -1}
        self._last_signature = signature
        self._last_result = dict(result)
        return result

    @staticmethod
    def _signature(history: list[dict[str, Any]]) -> tuple[Any, ...] | None:
        if not history:
            return None
        first = history[0]
        last = history[-1]
        last_values = last.get("values", {})
        return (
            len(history),
            first.get("ts"),
            last.get("ts"),
            last_values.get("hr"),
            last_values.get("spo2"),
            last_values.get("sbp"),
            last_values.get("dbp"),
            last_values.get("map"),
            last_values.get("rr"),
            last_values.get("temp"),
        )
