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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _shock_index_from_values(values: dict[str, Any]) -> float:
    shock_index = _safe_float(values.get("shock_index"), -1.0)
    if shock_index >= 0:
        return shock_index
    sbp = _safe_float(values.get("sbp"))
    hr = _safe_float(values.get("hr"))
    if sbp <= 0:
        return 0.0
    return hr / sbp


def _window_points(history: list[dict[str, Any]], hours: float) -> list[dict[str, Any]]:
    if not history:
        return []
    last_ts = _parse_iso(history[-1].get("ts", ""))
    if last_ts is None:
        return history
    threshold = last_ts.timestamp() - (hours * 3600.0)
    selected = [
        point
        for point in history
        if (_parse_iso(point.get("ts", "")) or last_ts).timestamp() >= threshold
    ]
    return selected or [history[-1]]


def _fraction(points: list[dict[str, Any]], predicate) -> float:
    if not points:
        return 0.0
    matches = sum(1 for point in points if predicate(point))
    return matches / len(points)


def _history_delta(points: list[dict[str, Any]], key: str) -> float:
    if len(points) < 2:
        return 0.0
    return _value_from_point(points[-1], key) - _value_from_point(points[0], key)


def _history_shock_delta(points: list[dict[str, Any]]) -> float:
    if len(points) < 2:
        return 0.0
    return _shock_index_from_values(points[-1].get("values", {})) - _shock_index_from_values(
        points[0].get("values", {})
    )


def _positive_rise(value: float) -> float:
    return max(0.0, value)


def _positive_drop(value: float) -> float:
    return max(0.0, -value)


def _resolve_scenario_family(scenario_key: str, pathology: str) -> str:
    text = f"{scenario_key} {pathology}".strip().lower()
    if "recovery_copy_patient1" in text or "constantes normales" in text:
        return "stable_reference"
    if "pneumonia_ira" in text or "pneumopathie" in text or "ira post-op" in text:
        return "pneumonia_ira"
    if "sepsis_progressive" in text or "sepsis" in text:
        return "sepsis_progressive"
    if "hemorrhage_low_grade" in text or "bas bruit" in text:
        return "hemorrhage_low_grade"
    if "hemorrhage_j2" in text or "hemorragie brutale" in text or "hemorragie j+2" in text:
        return "hemorrhage_j2"
    if "pulmonary_embolism" in text or "embolie pulmonaire" in text:
        return "pulmonary_embolism"
    if "pain_postop" in text or "douleur post-op" in text:
        return "pain_postop_uncontrolled"
    if "cardiac_postop_slow" in text or "cardiaque post-op lente" in text:
        return "cardiac_postop_slow"
    if "cardiac_postop_complication" in text or "cardiaque post-op rapide" in text:
        return "cardiac_postop_complication"
    return "generic"


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


def compute_immediate_criticality(last_vitals: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    spo2 = _safe_float(last_vitals.get("spo2"))
    hr = _safe_float(last_vitals.get("hr"))
    rr = _safe_float(last_vitals.get("rr"))
    temp = _safe_float(last_vitals.get("temp"))
    map_value = _safe_float(last_vitals.get("map"))
    shock_index = _safe_float(last_vitals.get("shock_index"))
    if shock_index <= 0:
        shock_index = _shock_index_from_values(last_vitals)

    score = 0
    triggers: list[str] = []

    def add_trigger(condition: bool, points: int, message: str) -> None:
        nonlocal score
        if condition:
            score += points
            triggers.append(message)

    spo2_critical = _safe_float(thresholds.get("spo2", {}).get("critical"), 90.0)
    hr_critical = _safe_float(thresholds.get("hr", {}).get("critical"), 140.0)
    rr_critical = _safe_float(thresholds.get("rr", {}).get("critical"), 30.0)
    temp_high_critical = _safe_float(thresholds.get("temp", {}).get("critical"), 39.0)
    temp_low_critical = _safe_float(thresholds.get("temp", {}).get("low_critical"), 36.0)
    map_critical = _safe_float(thresholds.get("map", {}).get("critical"), 65.0)
    shock_critical = _safe_float(thresholds.get("shock_index", {}).get("critical"), 1.0)

    add_trigger(spo2 < spo2_critical, 35, f"SpO2 {int(round(spo2))}% < {int(round(spo2_critical))}%")
    add_trigger(hr >= hr_critical, 18, f"FC {int(round(hr))} >= {int(round(hr_critical))} bpm")
    add_trigger(rr >= rr_critical, 18, f"FR {int(round(rr))} >= {int(round(rr_critical))}/min")
    add_trigger(
        temp >= temp_high_critical or temp <= temp_low_critical,
        14,
        f"TC {round(temp, 1)} hors zone critique",
    )
    add_trigger(map_value < map_critical, 35, f"TAM {int(round(map_value))} < {int(round(map_critical))}")
    add_trigger(shock_index >= shock_critical, 20, f"Shock index {shock_index:.2f} >= {shock_critical:.1f}")

    capped_score = min(100, score)
    if capped_score >= 60:
        level = "critique"
    elif capped_score > 0:
        level = "seuil_critique_franchi"
    else:
        level = "stable"

    return {
        "score": capped_score,
        "level": level,
        "active_threshold_count": len(triggers),
        "triggered_thresholds": triggers,
        "reference": "seuils_immediats",
    }


def compute_evolving_risk(
    history: list[dict[str, Any]],
    thresholds: dict[str, Any],
    scenario_key: str = "",
    pathology: str = "",
) -> dict[str, Any]:
    if not history:
        return {
            "score": 0,
            "level": "faible",
            "signal_count": 0,
            "signals": ["Historique indisponible"],
            "reference": "J0_to_now",
        }

    course = derive_course_features(history)
    scenario_family = _resolve_scenario_family(scenario_key, pathology)
    first_values = history[0].get("values", {})
    last_values = history[-1].get("values", {})
    one_hour = _window_points(history, 1)
    six_hours = _window_points(history, 6)
    twenty_four_hours = _window_points(history, 24)

    score = 0
    score_cap = 100
    signals: list[str] = []

    def add_signal(condition: bool, points: int, message: str) -> None:
        nonlocal score
        if condition:
            score += points
            signals.append(message)

    def apply_penalty(condition: bool, points: int, message: str) -> None:
        nonlocal score
        if condition:
            score -= points
            signals.append(message)

    spo2_info = _safe_float(thresholds.get("spo2", {}).get("info"), 94.0)
    spo2_warning = _safe_float(thresholds.get("spo2", {}).get("warning"), 92.0)
    hr_info = _safe_float(thresholds.get("hr", {}).get("info"), 105.0)
    rr_info = _safe_float(thresholds.get("rr", {}).get("info"), 22.0)
    temp_info = _safe_float(thresholds.get("temp", {}).get("info"), 38.0)
    temp_warning = _safe_float(thresholds.get("temp", {}).get("warning"), 38.5)
    temp_low = _safe_float(thresholds.get("temp", {}).get("low_critical"), 36.0)
    map_warning = _safe_float(thresholds.get("map", {}).get("warning"), 70.0)
    shock_warning = _safe_float(thresholds.get("shock_index", {}).get("warning"), 0.9)

    latest_spo2 = _safe_float(last_values.get("spo2"))
    latest_hr = _safe_float(last_values.get("hr"))
    latest_rr = _safe_float(last_values.get("rr"))
    latest_temp = _safe_float(last_values.get("temp"))
    latest_map = _safe_float(last_values.get("map"))
    latest_sbp = _safe_float(last_values.get("sbp"))
    latest_dbp = _safe_float(last_values.get("dbp"))
    last_shock = _shock_index_from_values(last_values)
    first_shock = _shock_index_from_values(first_values)

    spo2_drop_course = _positive_drop(course["spo2_delta_j0"])
    map_drop_course = _positive_drop(course["map_delta_j0"])
    hr_rise_course = _positive_rise(course["hr_delta_j0"])
    rr_rise_course = _positive_rise(course["rr_delta_j0"])
    temp_rise_course = _positive_rise(course["temp_delta_j0"])
    temp_drop_course = _positive_drop(course["temp_delta_j0"])
    shock_rise_course = _positive_rise(last_shock - first_shock)
    sbp_drop_course = _positive_drop(_safe_float(last_values.get("sbp")) - _safe_float(first_values.get("sbp")))
    dbp_drop_course = _positive_drop(_safe_float(last_values.get("dbp")) - _safe_float(first_values.get("dbp")))

    spo2_drop_1h = _positive_drop(_history_delta(one_hour, "spo2"))
    map_drop_1h = _positive_drop(_history_delta(one_hour, "map"))
    hr_rise_1h = _positive_rise(_history_delta(one_hour, "hr"))
    rr_rise_1h = _positive_rise(_history_delta(one_hour, "rr"))
    shock_rise_1h = _positive_rise(_history_shock_delta(one_hour))
    sbp_drop_1h = _positive_drop(_history_delta(one_hour, "sbp"))

    map_drop_6h = _positive_drop(_history_delta(six_hours, "map"))
    hr_rise_6h = _positive_rise(_history_delta(six_hours, "hr"))
    rr_rise_6h = _positive_rise(_history_delta(six_hours, "rr"))
    temp_rise_6h = _positive_rise(_history_delta(six_hours, "temp"))
    shock_rise_6h = _positive_rise(_history_shock_delta(six_hours))
    dbp_drop_6h = _positive_drop(_history_delta(six_hours, "dbp"))

    map_drop_24h = _positive_drop(_history_delta(twenty_four_hours, "map"))
    hr_rise_24h = _positive_rise(_history_delta(twenty_four_hours, "hr"))
    shock_rise_24h = _positive_rise(_history_shock_delta(twenty_four_hours))

    spo2_low_fraction_1h = _fraction(one_hour, lambda point: _value_from_point(point, "spo2") <= spo2_info)
    spo2_low_fraction_6h = _fraction(six_hours, lambda point: _value_from_point(point, "spo2") <= spo2_info)
    map_low_fraction_6h = _fraction(six_hours, lambda point: _value_from_point(point, "map") < map_warning)
    temp_high_fraction_6h = _fraction(six_hours, lambda point: _value_from_point(point, "temp") >= temp_info)
    rr_high_fraction_1h = _fraction(one_hour, lambda point: _value_from_point(point, "rr") >= rr_info)
    rr_high_fraction_6h = _fraction(six_hours, lambda point: _value_from_point(point, "rr") >= rr_info)

    if scenario_family == "stable_reference":
        add_signal(latest_spo2 <= spo2_warning, 10, "Desaturation inattendue sur un patient temoin")
        add_signal(latest_map < map_warning, 12, "Baisse hemodynamique inattendue depuis J0")
        add_signal(latest_temp >= temp_info or latest_temp <= temp_low, 8, "Temperature anormale sur un cas de reference")
        add_signal(shock_rise_course >= 0.2, 10, "Shock index en hausse anormale par rapport a J0")
        add_signal(hr_rise_course >= 12 and latest_rr >= rr_info, 8, "Reponse physiologique anormale pour le cas temoin")
    elif scenario_family == "pneumonia_ira":
        add_signal(latest_spo2 <= spo2_info, 12, f"SpO2 basse ({int(round(latest_spo2))}%)")
        add_signal(latest_spo2 <= spo2_warning, 12, "SpO2 installee sous 92%")
        add_signal(spo2_drop_course >= 3, 12, f"SpO2 en baisse de {int(round(spo2_drop_course))} points depuis J0")
        add_signal(spo2_drop_course >= 6, 8, "Desaturation majeure sur la trajectoire")
        add_signal(latest_rr >= rr_info, 10, f"FR elevee ({int(round(latest_rr))}/min)")
        add_signal(rr_rise_course >= 4, 10, f"FR en hausse de {int(round(rr_rise_course))}/min depuis J0")
        add_signal(rr_rise_6h >= 2, 6, "Aggravation respiratoire recente sur les 6 dernieres heures")
        add_signal(latest_temp >= temp_info, 8, f"Temperature elevee ({round(latest_temp, 1)} C)")
        add_signal(temp_rise_course >= 0.5 or temp_rise_6h >= 0.2, 8, "Temperature en hausse sur la trajectoire")
        add_signal(temp_high_fraction_6h >= 0.4, 8, "Temperature anormale persistante sur les 6 dernieres heures")
        add_signal(spo2_low_fraction_6h >= 0.4, 10, "Desaturation persistante sur plusieurs heures")
        add_signal(latest_spo2 <= spo2_info and latest_rr >= rr_info, 10, "Desaturation + polypnee compatibles avec une complication respiratoire")
        add_signal(latest_map < map_warning, 4, "Retentissement hemodynamique secondaire")
    elif scenario_family == "sepsis_progressive":
        add_signal(latest_temp >= temp_info or latest_temp <= temp_low, 12, "Temperature anormale actuellement")
        add_signal(temp_rise_course >= 1.0, 12, f"Temperature en hausse de {round(temp_rise_course, 1)} C depuis J0")
        add_signal(temp_high_fraction_6h >= 0.4, 10, "Temperature anormale persistante sur les dernieres heures")
        add_signal(latest_hr >= hr_info, 8, f"FC elevee ({int(round(latest_hr))} bpm)")
        add_signal(hr_rise_course >= 10, 10, f"FC en hausse de {int(round(hr_rise_course))} bpm depuis J0")
        add_signal(latest_rr >= rr_info, 8, f"FR elevee ({int(round(latest_rr))}/min)")
        add_signal(rr_rise_course >= 4, 8, f"FR en hausse de {int(round(rr_rise_course))}/min depuis J0")
        add_signal(dbp_drop_course >= 6 or dbp_drop_6h >= 3, 12, "Baisse diastolique compatible avec une vasoplegie")
        add_signal(map_drop_course >= 8, 10, f"TAM en baisse de {int(round(map_drop_course))} points depuis J0")
        add_signal(latest_map < map_warning, 8, "TAM basse compatible avec une vasoplegie")
        add_signal(shock_rise_course >= 0.15 or shock_rise_6h >= 0.08, 8, "Shock index en hausse sur la trajectoire")
        add_signal(
            (latest_temp >= temp_info or latest_temp <= temp_low) and latest_rr >= rr_info and latest_hr >= hr_info,
            12,
            "Cluster FC + FR + temperature compatible avec un sepsis",
        )
        add_signal(
            (dbp_drop_course >= 6 or latest_map < map_warning) and temp_rise_course >= 0.8,
            10,
            "Retentissement hemodynamique progressif compatible avec un sepsis",
        )
    elif scenario_family == "hemorrhage_low_grade":
        add_signal(hr_rise_course >= 8, 12, f"FC en hausse de {int(round(hr_rise_course))} bpm depuis J0")
        add_signal(map_drop_course >= 6, 12, f"TAM en baisse de {int(round(map_drop_course))} points depuis J0")
        add_signal(dbp_drop_course >= 2, 6, "Baisse diastolique progressive")
        add_signal(map_drop_24h >= 4, 8, "Baisse lente de TAM sur 24h")
        add_signal(hr_rise_24h >= 6, 8, "Tachycardie compensatrice progressive sur 24h")
        add_signal(shock_rise_course >= 0.15 or shock_rise_24h >= 0.08, 10, "Shock index en hausse depuis J0")
        add_signal(last_shock >= shock_warning, 8, f"Shock index eleve ({last_shock:.2f})")
        add_signal(latest_temp < temp_info and temp_rise_course < 0.5, 4, "Absence de fievre franche compatible avec un saignement a bas bruit")
        add_signal(
            hr_rise_course >= 8 and map_drop_course >= 6 and shock_rise_course >= 0.15,
            12,
            "Association FC en hausse + TAM en baisse + shock index en hausse",
        )
        apply_penalty(latest_temp >= temp_info, 12, "Temperature elevee peu compatible avec une hemorragie lente isolee")
    elif scenario_family == "hemorrhage_j2":
        add_signal(hr_rise_1h >= 8, 14, f"FC en hausse rapide de {int(round(hr_rise_1h))} bpm sur 1h")
        add_signal(map_drop_1h >= 8, 16, f"TAM en baisse de {int(round(map_drop_1h))} points sur 1h")
        add_signal(sbp_drop_1h >= 10, 10, f"SBP en baisse de {int(round(sbp_drop_1h))} points sur 1h")
        add_signal(shock_rise_1h >= 0.2, 12, f"Shock index en hausse de {shock_rise_1h:.2f} sur 1h")
        add_signal(last_shock >= shock_warning, 10, f"Shock index eleve ({last_shock:.2f})")
        add_signal(latest_map < map_warning, 12, f"TAM basse ({int(round(latest_map))})")
        add_signal(latest_sbp < 100, 8, f"SBP basse ({int(round(latest_sbp))})")
        add_signal(
            hr_rise_1h >= 8 and map_drop_1h >= 8 and shock_rise_1h >= 0.2,
            14,
            "Bascule rapide FC + TAM + shock index compatible avec une hemorragie brutale",
        )
        apply_penalty(latest_temp >= temp_info, 10, "Temperature elevee peu compatible avec une hemorragie brutale isolee")
    elif scenario_family == "pulmonary_embolism":
        add_signal(latest_spo2 <= spo2_info, 12, f"SpO2 basse ({int(round(latest_spo2))}%)")
        add_signal(latest_spo2 <= spo2_warning, 12, "SpO2 installee sous 92%")
        add_signal(spo2_drop_1h >= 3, 14, f"SpO2 en baisse de {int(round(spo2_drop_1h))} points sur 1h")
        add_signal(latest_rr >= rr_info, 10, f"FR elevee ({int(round(latest_rr))}/min)")
        add_signal(rr_rise_1h >= 4, 10, f"FR en hausse de {int(round(rr_rise_1h))}/min sur 1h")
        add_signal(latest_hr >= hr_info, 8, f"FC elevee ({int(round(latest_hr))} bpm)")
        add_signal(hr_rise_1h >= 8, 10, f"FC en hausse de {int(round(hr_rise_1h))} bpm sur 1h")
        add_signal(map_drop_1h >= 5 or shock_rise_1h >= 0.15, 10, "Retentissement hemodynamique recent")
        add_signal(
            latest_spo2 <= spo2_info and latest_rr >= rr_info and latest_hr >= hr_info,
            12,
            "Desaturation + polypnee + tachycardie compatibles avec une EP",
        )
        apply_penalty(latest_temp >= temp_info, 4, "Temperature elevee oriente plutot vers un mecanisme infectieux")
    elif scenario_family == "pain_postop_uncontrolled":
        score_cap = 65
        add_signal(latest_hr >= 95, 8, f"FC reactive ({int(round(latest_hr))} bpm)")
        add_signal(hr_rise_6h >= 6, 8, f"FC en hausse de {int(round(hr_rise_6h))} bpm sur 6h")
        add_signal(latest_rr >= 18, 6, f"FR moderee a {int(round(latest_rr))}/min")
        add_signal(rr_rise_6h >= 2, 4, "FR legerement en hausse sur 6h")
        add_signal(latest_sbp >= 130 or _positive_rise(_history_delta(six_hours, "sbp")) >= 6, 8, "Reponse tensionnelle compatible avec la douleur")
        add_signal(latest_spo2 >= spo2_info and latest_map >= map_warning and latest_temp < temp_info, 10, "Oxygenation et hemodynamique preservees, pattern compatible avec une douleur")
        add_signal(latest_hr >= 95 and latest_sbp >= 130 and latest_temp < temp_info, 8, "FC + TA elevees sans argument infectieux fort")
        apply_penalty(latest_temp >= temp_info, 12, "Temperature elevee peu compatible avec une douleur isolee")
        apply_penalty(latest_spo2 < spo2_info, 12, "Desaturation peu compatible avec une douleur simple")
        apply_penalty(latest_map < map_warning or last_shock >= shock_warning, 12, "Retentissement circulatoire peu compatible avec une douleur simple")
    elif scenario_family == "cardiac_postop_slow":
        add_signal(map_drop_course >= 10, 14, f"TAM en baisse de {int(round(map_drop_course))} points depuis J0")
        add_signal(map_drop_6h >= 4, 8, "Baisse progressive de TAM sur 6h")
        add_signal(latest_map < map_warning, 10, f"TAM basse ({int(round(latest_map))})")
        add_signal(hr_rise_course >= 12, 10, f"FC en hausse de {int(round(hr_rise_course))} bpm depuis J0")
        add_signal(latest_hr >= hr_info, 8, f"FC elevee ({int(round(latest_hr))} bpm)")
        add_signal(shock_rise_course >= 0.2 or shock_rise_6h >= 0.08, 12, "Shock index en hausse sur la trajectoire")
        add_signal(last_shock >= shock_warning, 10, f"Shock index eleve ({last_shock:.2f})")
        add_signal(spo2_drop_course >= 1 and spo2_drop_course <= 4, 6, "Baisse moderee de l'oxygenation")
        add_signal(map_low_fraction_6h >= 0.4, 8, "TAM basse persistante sur les dernieres heures")
        add_signal(
            latest_temp < temp_info and latest_rr < 25 and latest_spo2 >= 92,
            10,
            "Profil de bas debit avec temperature normale et retentissement respiratoire limite",
        )
        add_signal(
            map_drop_course >= 10 and (hr_rise_course >= 12 or shock_rise_course >= 0.2),
            12,
            "Baisse de debit progressive compatible avec une complication cardiaque lente",
        )
        apply_penalty(latest_temp >= temp_info, 6, "Temperature elevee moins compatible avec une complication cardiaque isolee")
        apply_penalty(latest_spo2 < 90 and latest_rr >= 25, 8, "Tableau trop respiratoire pour une complication cardiaque isolee")
    elif scenario_family == "cardiac_postop_complication":
        add_signal(map_drop_1h >= 8, 16, f"TAM en baisse de {int(round(map_drop_1h))} points sur 1h")
        add_signal(latest_map < map_warning, 12, f"TAM basse ({int(round(latest_map))})")
        add_signal(shock_rise_1h >= 0.2, 14, f"Shock index en hausse de {shock_rise_1h:.2f} sur 1h")
        add_signal(last_shock >= shock_warning, 10, f"Shock index eleve ({last_shock:.2f})")
        add_signal(hr_rise_1h >= 10, 12, f"FC en hausse de {int(round(hr_rise_1h))} bpm sur 1h")
        add_signal(latest_hr >= hr_info, 8, f"FC elevee ({int(round(latest_hr))} bpm)")
        add_signal(_positive_drop(_history_delta(one_hour, "spo2")) >= 1 and _positive_drop(_history_delta(one_hour, "spo2")) <= 4, 6, "Oxygenation en baisse recente mais moderee")
        add_signal(latest_spo2 <= spo2_info and latest_spo2 >= 90, 6, f"SpO2 moderement basse ({int(round(latest_spo2))}%)")
        add_signal(
            latest_temp < temp_info and latest_rr < 25 and latest_spo2 >= 90,
            12,
            "Profil de bas debit avec temperature normale et atteinte respiratoire limitee",
        )
        add_signal(
            map_drop_1h >= 8 and shock_rise_1h >= 0.2 and hr_rise_1h >= 10,
            14,
            "Bascule rapide TAM + shock index + FC compatible avec une complication cardiaque rapide",
        )
        apply_penalty(latest_temp >= temp_info, 6, "Temperature elevee moins compatible avec une complication cardiaque isolee")
        apply_penalty(latest_spo2 < 90 and latest_rr >= 25, 10, "Desaturation severe avec polypnee importante, pattern moins specifique du cardiaque")
    else:
        add_signal(latest_spo2 <= spo2_info, 8, f"SpO2 basse ({int(round(latest_spo2))}%)")
        add_signal(spo2_drop_course >= 3, 10, f"SpO2 en baisse de {int(round(spo2_drop_course))} points depuis J0")
        add_signal(latest_hr >= hr_info, 8, f"FC elevee ({int(round(latest_hr))} bpm)")
        add_signal(hr_rise_course >= 15, 10, f"FC en hausse de {int(round(hr_rise_course))} bpm depuis J0")
        add_signal(latest_rr >= rr_info, 8, f"FR elevee ({int(round(latest_rr))}/min)")
        add_signal(rr_rise_course >= 6, 10, f"FR en hausse de {int(round(rr_rise_course))}/min depuis J0")
        add_signal(latest_temp >= temp_info or latest_temp <= temp_low, 8, f"Temperature anormale ({round(latest_temp, 1)} C)")
        add_signal(temp_rise_course >= 1.0 or temp_drop_course >= 0.5, 10, "Temperature qui s'eloigne de la reference")
        add_signal(latest_map < map_warning, 12, f"TAM basse ({int(round(latest_map))})")
        add_signal(map_drop_course >= 10, 12, f"TAM en baisse de {int(round(map_drop_course))} points depuis J0")
        add_signal(last_shock >= shock_warning, 10, f"Shock index eleve ({last_shock:.2f})")
        add_signal(shock_rise_course >= 0.2, 8, "Shock index en hausse depuis J0")
        add_signal(spo2_low_fraction_1h >= 0.5, 8, "Desaturation persistante sur la derniere heure")
        add_signal(rr_high_fraction_1h >= 0.5 or rr_high_fraction_6h >= 0.4, 8, "FR elevee persistante")
        add_signal(
            latest_spo2 <= spo2_info and latest_rr >= rr_info,
            8,
            "Desaturation associee a une polypnee",
        )
        add_signal(
            latest_map < map_warning and (latest_hr >= hr_info or last_shock >= shock_warning),
            8,
            "Retentissement circulatoire associe a une tachycardie",
        )

    capped_score = min(score_cap, max(0, score))
    if capped_score >= 75:
        level = "tres_eleve"
    elif capped_score >= 50:
        level = "eleve"
    elif capped_score >= 25:
        level = "modere"
    else:
        level = "faible"

    return {
        "score": capped_score,
        "level": level,
        "signal_count": len(signals),
        "signals": signals,
        "reference": "J0_to_now",
        "course_hours": course["course_hours"],
        "scenario_family": scenario_family,
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
