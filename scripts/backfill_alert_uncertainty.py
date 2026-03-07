from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def load_rules() -> tuple[dict, dict[str, dict]]:
    config_path = Path(os.getenv("ALERT_RULES_PATH", "/workspace/config/alert_rules.json"))
    if not config_path.exists():
        config_path = Path("/app/config/alert_rules.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    rules_by_id = {rule["id"]: rule for rule in payload.get("rules", [])}
    return payload, rules_by_id


def dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'postgres')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'postop')} "
        f"user={os.getenv('POSTGRES_USER', 'postop')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'postop')}"
    )


def build_uncertainty_payload(ruleset: dict, rule: dict, snapshot: dict) -> dict:
    scenario = str(snapshot.get("scenario") or "")
    default_profile = ruleset.get("default_uncertainty", {})
    profile = ruleset.get("uncertainty_profiles", {}).get(scenario, {})
    merged_profile = {
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

    conditions = flatten_conditions(rule["logic"])
    has_duration = any("duration_seconds" in condition for condition in conditions)
    has_trend = any("trend" in condition for condition in conditions)
    multi_signal = len(conditions) >= 2
    confidence = {"INFO": 45, "WARNING": 60, "CRITICAL": 75}.get(rule["level"], 50)
    if multi_signal:
        confidence += 10
    if has_duration:
        confidence += 5
    if has_trend:
        confidence += 5
    confidence = min(confidence, 95)

    remeasure = int(merged_profile["remeasure_minutes"].get(rule["level"], 0))
    evidence_mode = "multi_signal" if multi_signal else "single_signal"
    if has_duration:
        evidence_mode += "+persistence"
    if has_trend:
        evidence_mode += "+trend"

    if rule["level"] == "INFO":
        suspicion = "suspicion_precoce"
    elif rule["level"] == "WARNING":
        suspicion = "suspicion_a_confirmer"
    elif multi_signal or has_trend:
        suspicion = "degradation_confirmee"
    else:
        suspicion = "suspicion_forte"

    if remeasure > 0:
        note = (
            f"Suspicion a confirmer. Faux positif {merged_profile['false_positive_risk']}, "
            f"faux negatif {merged_profile['false_negative_risk']}. Recontrole conseille dans {remeasure} min."
        )
    else:
        note = (
            f"Evenement severe. Faux positif {merged_profile['false_positive_risk']}, "
            f"faux negatif {merged_profile['false_negative_risk']}. Reevaluation immediate."
        )

    return {
        "suspicion_stage": suspicion,
        "confidence_score": confidence,
        "evidence_mode": evidence_mode,
        "false_positive_risk": merged_profile["false_positive_risk"],
        "false_negative_risk": merged_profile["false_negative_risk"],
        "remeasure_minutes": remeasure,
        "false_positive_examples": merged_profile["false_positive_examples"],
        "false_negative_examples": merged_profile["false_negative_examples"],
        "uncertainty_note": note,
    }


def flatten_conditions(logic: dict) -> list[dict]:
    if "all" in logic:
        conditions: list[dict] = []
        for condition in logic["all"]:
            conditions.extend(flatten_conditions(condition))
        return conditions
    if "any" in logic:
        conditions: list[dict] = []
        for condition in logic["any"]:
            conditions.extend(flatten_conditions(condition))
        return conditions
    return [logic]


def main() -> int:
    ruleset, rules_by_id = load_rules()
    updated = 0
    skipped = 0
    with psycopg.connect(dsn(), row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, rule_id, level, metric_snapshot
            FROM alerts
            WHERE (metric_snapshot->>'uncertainty_note') IS NULL
               OR (metric_snapshot->>'confidence_score') IS NULL
               OR (metric_snapshot->>'suspicion_stage') IS NULL
            ORDER BY id
            """
        )
        rows = cur.fetchall()
        for row in rows:
            rule = rules_by_id.get(row["rule_id"])
            snapshot = row["metric_snapshot"] or {}
            if not rule or not isinstance(snapshot, dict):
                skipped += 1
                continue
            enriched = {**snapshot, **build_uncertainty_payload(ruleset, rule, snapshot)}
            cur.execute(
                "UPDATE alerts SET metric_snapshot = %s::jsonb WHERE id = %s",
                (json.dumps(enriched), row["id"]),
            )
            updated += 1
        conn.commit()
    print(json.dumps({"updated": updated, "skipped": skipped}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
