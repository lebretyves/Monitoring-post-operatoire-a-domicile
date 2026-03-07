from __future__ import annotations

import json
from pathlib import Path


def validate_rule(rule: dict) -> list[str]:
    errors: list[str] = []
    if "id" not in rule:
        errors.append("missing id")
    if rule.get("level") not in {"INFO", "WARNING", "CRITICAL"}:
        errors.append(f"invalid level for {rule.get('id', '<unknown>')}")
    if "logic" not in rule:
        errors.append(f"missing logic for {rule.get('id', '<unknown>')}")
    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    rules_path = root / "config" / "alert_rules.json"
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for rule in payload.get("rules", []):
        errors.extend(validate_rule(rule))
    if errors:
        raise SystemExit("Rule validation failed:\n- " + "\n- ".join(errors))
    print(f"{len(payload.get('rules', []))} rules validated from {rules_path}")


if __name__ == "__main__":
    main()
