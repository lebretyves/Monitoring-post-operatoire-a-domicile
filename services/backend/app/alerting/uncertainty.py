from __future__ import annotations

from typing import Any


def build_uncertainty_payload(ruleset: dict[str, Any], rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    profile = uncertainty_profile(ruleset, snapshot)
    evidence = logic_evidence(rule["logic"])
    level = rule["level"]
    remeasure = remeasure_minutes(profile, level)
    return {
        "suspicion_stage": suspicion_stage(level, evidence),
        "confidence_score": confidence_score(level, evidence),
        "evidence_mode": evidence["mode"],
        "false_positive_risk": profile["false_positive_risk"],
        "false_negative_risk": profile["false_negative_risk"],
        "remeasure_minutes": remeasure,
        "false_positive_examples": profile["false_positive_examples"],
        "false_negative_examples": profile["false_negative_examples"],
        "uncertainty_note": uncertainty_note(profile, remeasure),
    }


def uncertainty_profile(ruleset: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    scenario = str(snapshot.get("scenario") or "")
    default_profile = ruleset.get("default_uncertainty", {})
    profile = ruleset.get("uncertainty_profiles", {}).get(scenario, {})
    return {
        "false_positive_risk": profile.get("false_positive_risk", default_profile.get("false_positive_risk", "medium")),
        "false_negative_risk": profile.get("false_negative_risk", default_profile.get("false_negative_risk", "medium")),
        "remeasure_minutes": profile.get("remeasure_minutes", default_profile.get("remeasure_minutes", {})),
        "false_positive_examples": profile.get(
            "false_positive_examples",
            default_profile.get("false_positive_examples", []),
        ),
        "false_negative_examples": profile.get(
            "false_negative_examples",
            default_profile.get("false_negative_examples", []),
        ),
    }


def remeasure_minutes(profile: dict[str, Any], level: str) -> int:
    schedule = profile.get("remeasure_minutes", {})
    try:
        return int(schedule.get(level, 0))
    except (TypeError, ValueError):
        return 0


def uncertainty_note(profile: dict[str, Any], remeasure: int) -> str:
    fp = profile["false_positive_risk"]
    fn = profile["false_negative_risk"]
    if remeasure > 0:
        return (
            f"Suspicion a confirmer. Faux positif {fp}, faux negatif {fn}. "
            f"Recontrole conseille dans {remeasure} min."
        )
    return f"Evenement severe. Faux positif {fp}, faux negatif {fn}. Reevaluation immediate."


def suspicion_stage(level: str, evidence: dict[str, Any]) -> str:
    if level == "INFO":
        return "suspicion_precoce"
    if level == "WARNING":
        return "suspicion_a_confirmer"
    if evidence["multi_signal"] or evidence["has_trend"]:
        return "degradation_confirmee"
    return "suspicion_forte"


def confidence_score(level: str, evidence: dict[str, Any]) -> int:
    score = {"INFO": 45, "WARNING": 60, "CRITICAL": 75}.get(level, 50)
    if evidence["multi_signal"]:
        score += 10
    if evidence["has_duration"]:
        score += 5
    if evidence["has_trend"]:
        score += 5
    return min(score, 95)


def logic_evidence(logic: dict[str, Any]) -> dict[str, Any]:
    conditions = flatten_conditions(logic)
    has_duration = any("duration_seconds" in condition for condition in conditions)
    has_trend = any("trend" in condition for condition in conditions)
    multi_signal = len(conditions) >= 2
    mode_parts = []
    mode_parts.append("multi_signal" if multi_signal else "single_signal")
    if has_duration:
        mode_parts.append("persistence")
    if has_trend:
        mode_parts.append("trend")
    return {
        "count": len(conditions),
        "has_duration": has_duration,
        "has_trend": has_trend,
        "multi_signal": multi_signal,
        "mode": "+".join(mode_parts),
    }


def flatten_conditions(logic: dict[str, Any]) -> list[dict[str, Any]]:
    if "all" in logic:
        conditions: list[dict[str, Any]] = []
        for condition in logic["all"]:
            conditions.extend(flatten_conditions(condition))
        return conditions
    if "any" in logic:
        conditions = []
        for condition in logic["any"]:
            conditions.extend(flatten_conditions(condition))
        return conditions
    return [logic]
