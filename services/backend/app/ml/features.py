from __future__ import annotations

from datetime import datetime
from typing import Any


COURSE_FEATURE_DEFAULTS = {
    "course_hours": 0.0,
    "hr_delta_j0": 0.0,
    "spo2_delta_j0": 0.0,
    "map_delta_j0": 0.0,
    "rr_delta_j0": 0.0,
    "temp_delta_j0": 0.0,
    "min_spo2_course": 0.0,
    "min_map_course": 0.0,
    "max_temp_course": 0.0,
}


def _value_from_point(point: dict[str, Any], key: str) -> float:
    values = point.get("values", {})
    return float(values.get(key, 0.0))


def derive_course_features(history: list[dict[str, Any]]) -> dict[str, float]:
    if not history:
        return dict(COURSE_FEATURE_DEFAULTS)

    first_point = history[0]
    last_point = history[-1]
    first_ts = first_point.get("ts", "")
    last_ts = last_point.get("ts", "")
    if first_ts and last_ts:
        course_hours = max(
            0.0,
            (
                (
                    datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                    - datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                ).total_seconds()
                / 3600.0
            ),
        )
    else:
        course_hours = 0.0

    return {
        "course_hours": round(course_hours, 2),
        "hr_delta_j0": round(_value_from_point(last_point, "hr") - _value_from_point(first_point, "hr"), 2),
        "spo2_delta_j0": round(_value_from_point(last_point, "spo2") - _value_from_point(first_point, "spo2"), 2),
        "map_delta_j0": round(_value_from_point(last_point, "map") - _value_from_point(first_point, "map"), 2),
        "rr_delta_j0": round(_value_from_point(last_point, "rr") - _value_from_point(first_point, "rr"), 2),
        "temp_delta_j0": round(_value_from_point(last_point, "temp") - _value_from_point(first_point, "temp"), 2),
        "min_spo2_course": round(min(_value_from_point(point, "spo2") for point in history), 2),
        "min_map_course": round(min(_value_from_point(point, "map") for point in history), 2),
        "max_temp_course": round(max(_value_from_point(point, "temp") for point in history), 2),
    }


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
