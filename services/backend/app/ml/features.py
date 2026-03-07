from __future__ import annotations

from typing import Any


def build_feature_matrix(history: list[dict[str, Any]]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in history:
        values = row.get("values", {})
        matrix.append(
            [
                float(values.get("hr", 0.0)),
                float(values.get("spo2", 0.0)),
                float(values.get("map", 0.0)),
                float(values.get("rr", 0.0)),
                float(values.get("temp", 0.0)),
            ]
        )
    return matrix
