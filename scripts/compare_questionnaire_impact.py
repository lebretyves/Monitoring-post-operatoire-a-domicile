from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import create_app  # noqa: E402


CASES_PATH = REPO_ROOT / "config" / "cases_catalog.json"
SIMULATION_PATH = REPO_ROOT / "config" / "simulation_scenarios.json"
OUTPUT_PATH = Path("/app/runtime/questionnaire_campaign_results.json")
TARGET_PATIENT_ID = "PAT-001"

DEFAULT_BASELINE = {
    "hr": 76.0,
    "spo2": 98.0,
    "sbp": 124.0,
    "dbp": 77.0,
    "rr": 16.0,
    "temp": 36.8,
}

EXPECTED_TOP_HYPOTHESIS = {
    "recovery_copy_patient1": None,
    "pneumonia_ira": "Complication respiratoire post-op (pneumopathie / IRA)",
    "hemorrhage_j2": "Hemorragie / hypovolemie possible",
    "hemorrhage_low_grade": "Hemorragie / hypovolemie possible",
    "pulmonary_embolism": "Embolie pulmonaire possible",
    "sepsis_progressive": "Sepsis / complication infectieuse possible",
    "pain_postop_uncontrolled": "Douleur post-op non controlee possible",
    "cardiac_postop_complication": "Complication cardiaque post-op possible",
    "cardiac_postop_slow": "Complication cardiaque post-op possible",
}

QUESTIONNAIRE_PAYLOADS = {
    "pneumonia_ira": {
        "responder": "ide",
        "comment": "dyspnee progressive avec toux, crachats purulents et frissons",
        "answers": [
            {"module_id": "respiratory_differential", "question_id": "dyspnea_onset", "answer": "progressif"},
            {"module_id": "respiratory_differential", "question_id": "chest_pain_type", "answer": "toux"},
            {"module_id": "respiratory_differential", "question_id": "cough", "answer": "yes"},
            {"module_id": "respiratory_differential", "question_id": "sputum", "answer": "purulent"},
            {"module_id": "infectious_differential", "question_id": "chills", "answer": "yes"},
        ],
    },
    "hemorrhage_j2": {
        "responder": "ide",
        "comment": "saignement visible avec pansement souille et malaise",
        "answers": [
            {"module_id": "hemodynamic_differential", "question_id": "visible_bleeding", "answer": "yes"},
            {"module_id": "hemodynamic_differential", "question_id": "dressing_saturated", "answer": "yes"},
            {"module_id": "hemodynamic_differential", "question_id": "syncope_malaise", "answer": "yes"},
        ],
    },
    "hemorrhage_low_grade": {
        "responder": "ide",
        "comment": "malaise discret avec pansement de plus en plus souille",
        "answers": [
            {"module_id": "hemodynamic_differential", "question_id": "dressing_saturated", "answer": "yes"},
            {"module_id": "hemodynamic_differential", "question_id": "syncope_malaise", "answer": "yes"},
        ],
    },
    "pulmonary_embolism": {
        "responder": "ide",
        "comment": "dyspnee brutale, douleur pleurale et mollet gonfle",
        "answers": [
            {"module_id": "respiratory_differential", "question_id": "dyspnea_onset", "answer": "brutal"},
            {"module_id": "respiratory_differential", "question_id": "chest_pain_type", "answer": "pleurale"},
            {"module_id": "respiratory_differential", "question_id": "cough", "answer": "no"},
            {"module_id": "respiratory_differential", "question_id": "sputum", "answer": "none"},
            {"module_id": "respiratory_differential", "question_id": "calf_pain_swelling", "answer": "yes"},
        ],
    },
    "sepsis_progressive": {
        "responder": "ide",
        "comment": "frissons avec foyer de plaie inflammatoire",
        "answers": [
            {"module_id": "infectious_differential", "question_id": "chills", "answer": "yes"},
            {"module_id": "infectious_differential", "question_id": "wound_redness", "answer": "yes"},
            {"module_id": "infectious_differential", "question_id": "wound_discharge", "answer": "yes"},
        ],
    },
    "pain_postop_uncontrolled": {
        "responder": "patient",
        "comment": "douleur surtout a la mobilisation, mieux apres antalgie",
        "answers": [
            {"module_id": "pain_differential", "question_id": "pain_at_rest", "answer": "moderate"},
            {"module_id": "pain_differential", "question_id": "pain_with_mobilization", "answer": "yes"},
            {"module_id": "pain_differential", "question_id": "pain_with_cough", "answer": "yes"},
            {"module_id": "pain_differential", "question_id": "improved_after_rest_or_analgesia", "answer": "yes"},
        ],
    },
    "cardiac_postop_complication": {
        "responder": "ide",
        "comment": "douleur thoracique oppressante avec palpitations",
        "answers": [
            {"module_id": "hemodynamic_differential", "question_id": "oppressive_chest_pain", "answer": "yes"},
            {"module_id": "hemodynamic_differential", "question_id": "palpitations", "answer": "yes"},
            {"module_id": "hemodynamic_differential", "question_id": "syncope_malaise", "answer": "yes"},
        ],
    },
    "cardiac_postop_slow": {
        "responder": "ide",
        "comment": "palpitations et oppression thoracique progressive",
        "answers": [
            {"module_id": "hemodynamic_differential", "question_id": "oppressive_chest_pain", "answer": "yes"},
            {"module_id": "hemodynamic_differential", "question_id": "palpitations", "answer": "yes"},
        ],
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clamp(metric: str, value: float, clamp_bounds: dict[str, list[float]]) -> float:
    low, high = clamp_bounds[metric]
    return max(float(low), min(float(high), value))


def build_reading(
    *,
    patient_id: str,
    ts: str,
    room: str,
    scenario_name: str,
    scenario_label: str,
    surgery_type: str,
    postop_day: int,
    values: dict[str, float],
    battery: int,
) -> dict[str, Any]:
    sbp = int(round(values["sbp"]))
    dbp = int(round(values["dbp"]))
    map_value = int(round(dbp + ((sbp - dbp) / 3.0)))
    return {
        "ts": ts,
        "patient_id": patient_id,
        "profile": "baseline_normale",
        "scenario": scenario_name,
        "scenario_label": scenario_label,
        "hr": int(round(values["hr"])),
        "spo2": int(round(values["spo2"])),
        "sbp": sbp,
        "dbp": dbp,
        "map": map_value,
        "rr": int(round(values["rr"])),
        "temp": round(values["temp"], 1),
        "room": room,
        "battery": battery,
        "postop_day": postop_day,
        "surgery_type": surgery_type,
        "shock_index": round(float(values["hr"]) / max(float(values["sbp"]), 1.0), 2),
    }


def build_case_history(case: dict[str, Any], scenario_def: dict[str, Any]) -> list[dict[str, Any]]:
    clamp_bounds = load_json(SIMULATION_PATH)["clamp"]
    baseline = dict(DEFAULT_BASELINE)
    baseline.update(case.get("baseline") or {})
    scenario_label = scenario_def["label"]
    postop_day = int(case["postop_day"])
    reference_ts = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
    total_minutes = int(
        sum(float(phase.get("duration_minutes", 0)) for phase in scenario_def.get("timeline", []))
    )
    if total_minutes <= 0:
        total_minutes = 120
    current_ts = reference_ts - timedelta(minutes=total_minutes)

    points: list[dict[str, Any]] = [
        build_reading(
            patient_id=TARGET_PATIENT_ID,
            ts=current_ts.isoformat().replace("+00:00", "Z"),
            room=case["room"],
            scenario_name=case["scenario"],
            scenario_label=scenario_label,
            surgery_type=case["surgery_type"],
            postop_day=postop_day,
            values=baseline,
            battery=99,
        )
    ]

    current_values = dict(baseline)
    initial_shift = (scenario_def.get("initial_shift_by_postop_day") or {}).get(str(postop_day))
    if isinstance(initial_shift, dict):
        current_ts += timedelta(minutes=max(60, total_minutes // 6))
        shifted = {
            metric: clamp(metric, baseline.get(metric, 0.0) + float(initial_shift.get(metric, 0.0)), clamp_bounds)
            for metric in DEFAULT_BASELINE
        }
        current_values = shifted
        points.append(
            build_reading(
                patient_id=TARGET_PATIENT_ID,
                ts=current_ts.isoformat().replace("+00:00", "Z"),
                room=case["room"],
                scenario_name=case["scenario"],
                scenario_label=scenario_label,
                surgery_type=case["surgery_type"],
                postop_day=postop_day,
                values=current_values,
                battery=98,
            )
        )

    timeline = scenario_def.get("timeline", [])
    for phase in timeline:
        duration = max(30, int(round(float(phase.get("duration_minutes", 60)))))
        instant_jump = phase.get("instant_jump") or {}
        if instant_jump:
            current_ts += timedelta(minutes=max(15, duration // 4))
            current_values = {
                metric: clamp(metric, current_values.get(metric, baseline.get(metric, 0.0)) + float(instant_jump.get(metric, 0.0)), clamp_bounds)
                for metric in DEFAULT_BASELINE
            }
            points.append(
                build_reading(
                    patient_id=TARGET_PATIENT_ID,
                    ts=current_ts.isoformat().replace("+00:00", "Z"),
                    room=case["room"],
                    scenario_name=case["scenario"],
                    scenario_label=scenario_label,
                    surgery_type=case["surgery_type"],
                    postop_day=postop_day,
                    values=current_values,
                    battery=max(65, 99 - len(points)),
                )
            )

        current_ts += timedelta(minutes=duration)
        target_shift = phase.get("target_shift")
        if isinstance(target_shift, dict):
            current_values = {
                metric: clamp(metric, baseline.get(metric, 0.0) + float(target_shift.get(metric, 0.0)), clamp_bounds)
                for metric in DEFAULT_BASELINE
            }
        else:
            trend = phase.get("trend_per_10min") or {}
            current_values = {
                metric: clamp(
                    metric,
                    current_values.get(metric, baseline.get(metric, 0.0))
                    + float(trend.get(metric, 0.0)) * (duration / 10.0),
                    clamp_bounds,
                )
                for metric in DEFAULT_BASELINE
            }
        points.append(
            build_reading(
                patient_id=TARGET_PATIENT_ID,
                ts=current_ts.isoformat().replace("+00:00", "Z"),
                room=case["room"],
                scenario_name=case["scenario"],
                scenario_label=scenario_label,
                surgery_type=case["surgery_type"],
                postop_day=postop_day,
                values=current_values,
                battery=max(60, 99 - len(points)),
            )
        )

    deduped: list[dict[str, Any]] = []
    seen_ts: set[str] = set()
    for point in points:
        if point["ts"] in seen_ts:
            continue
        deduped.append(point)
        seen_ts.add(point["ts"])
    return deduped


def seed_case(services: Any, case: dict[str, Any], scenario_def: dict[str, Any]) -> list[dict[str, Any]]:
    patient_id = TARGET_PATIENT_ID
    services.influx.clear_patient_history(patient_id)
    services.postgres.clear_patient_alerts(patient_id)
    if hasattr(services.postgres, "clear_patient_notifications"):
        services.postgres.clear_patient_notifications(patient_id)
    services.state.clear_patient(patient_id)
    services.last_vitals.pop(patient_id, None)
    services.postgres.update_patient_case(
        patient_id,
        {
            "full_name": case["full_name"],
            "profile": case["profile"],
            "surgery_type": case["surgery_type"],
            "postop_day": case["postop_day"],
            "risk_level": case["risk_level"],
            "room": case["room"],
            "history": case.get("history", []),
        },
    )

    readings = build_case_history(case, scenario_def)
    for reading in readings:
        services.state.push(reading)
        services.influx.write_vital(reading)
        for alert in services.alert_engine.evaluate(reading):
            services.postgres.store_alert(alert)
    services.last_vitals[patient_id] = readings[-1]
    return readings


def filter_questionnaire_payload(case: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any] | None:
    payload = QUESTIONNAIRE_PAYLOADS.get(case["scenario"])
    if not payload:
        return None
    selected_modules = {str(module.get("id")) for module in selection.get("modules", [])}
    answers = [answer for answer in payload["answers"] if answer["module_id"] in selected_modules]
    if not answers:
        return None
    return {
        "responder": payload["responder"],
        "comment": payload["comment"],
        "answers": answers,
    }


def alignment(expected_label: str | None, actual_label: str) -> str:
    if expected_label is None:
        return "n/a"
    return "yes" if expected_label == actual_label else "no"


def improvement_status(expected_label: str | None, baseline_label: str, questionnaire_label: str) -> str:
    if expected_label is None:
        return "n/a"
    baseline_match = baseline_label == expected_label
    questionnaire_match = questionnaire_label == expected_label
    if not baseline_match and questionnaire_match:
        return "improved"
    if baseline_match and questionnaire_match and baseline_label != questionnaire_label:
        return "changed_but_still_aligned"
    if baseline_match and not questionnaire_match:
        return "degraded"
    if baseline_label != questionnaire_label:
        return "changed_no_alignment_gain"
    return "unchanged"


def run_campaign() -> dict[str, Any]:
    cases_catalog = load_json(CASES_PATH)
    simulation_config = load_json(SIMULATION_PATH)
    scenario_catalog = simulation_config["scenario_catalog"]

    results: list[dict[str, Any]] = []
    app = create_app(test_mode=True)
    with TestClient(app) as client:
        services = client.app.state.services
        for case in cases_catalog["cases"]:
            scenario_def = scenario_catalog[case["scenario"]]
            seed_case(services, case, scenario_def)

            questionnaire_response = client.get(f"/api/llm/{TARGET_PATIENT_ID}/questionnaire")
            questionnaire_response.raise_for_status()
            selection = questionnaire_response.json()

            baseline_response = client.get(f"/api/llm/{TARGET_PATIENT_ID}/clinical-package")
            baseline_response.raise_for_status()
            baseline_payload = baseline_response.json()

            questionnaire_payload = filter_questionnaire_payload(case, selection)
            if questionnaire_payload:
                rerank_response = client.post(
                    f"/api/llm/{TARGET_PATIENT_ID}/clinical-package",
                    json={"questionnaire": questionnaire_payload},
                )
                rerank_response.raise_for_status()
                rerank_payload = rerank_response.json()
            else:
                rerank_payload = baseline_payload

            expected_label = EXPECTED_TOP_HYPOTHESIS.get(case["scenario"])
            baseline_top = baseline_payload["hypothesis_ranking"][0]["label"]
            baseline_top_percent = baseline_payload["hypothesis_ranking"][0].get("compatibility_percent")
            rerank_top = rerank_payload["hypothesis_ranking"][0]["label"]
            rerank_top_percent = rerank_payload["hypothesis_ranking"][0].get("compatibility_percent")

            results.append(
                {
                    "case_id": case["case_id"],
                    "case_label": case["case_label"],
                    "scenario": case["scenario"],
                    "scenario_label": scenario_def["label"],
                    "expected_top_hypothesis": expected_label,
                    "selected_modules": [module["id"] for module in selection.get("modules", [])],
                    "trigger_summary": selection.get("trigger_summary", []),
                    "baseline_top_hypothesis": baseline_top,
                    "baseline_top_percent": baseline_top_percent,
                    "baseline_aligned_with_scenario": alignment(expected_label, baseline_top),
                    "with_questionnaire_top_hypothesis": rerank_top,
                    "with_questionnaire_top_percent": rerank_top_percent,
                    "with_questionnaire_aligned_with_scenario": alignment(expected_label, rerank_top),
                    "questionnaire_used": questionnaire_payload is not None,
                    "questionnaire_payload": questionnaire_payload,
                    "comparison_status": improvement_status(expected_label, baseline_top, rerank_top),
                }
            )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "case_count": len(results),
        "aligned_without_questionnaire": sum(
            1 for item in results if item["baseline_aligned_with_scenario"] == "yes"
        ),
        "aligned_with_questionnaire": sum(
            1 for item in results if item["with_questionnaire_aligned_with_scenario"] == "yes"
        ),
        "improved_cases": [item["case_id"] for item in results if item["comparison_status"] == "improved"],
        "degraded_cases": [item["case_id"] for item in results if item["comparison_status"] == "degraded"],
        "results": results,
    }
    return summary


def print_report(summary: dict[str, Any]) -> None:
    print(
        "case_id | scenario_label | baseline_top | baseline_ok | with_questionnaire_top | with_questionnaire_ok | status"
    )
    for item in summary["results"]:
        print(
            f"{item['case_id']} | "
            f"{item['scenario_label']} | "
            f"{item['baseline_top_hypothesis']} ({item['baseline_top_percent']}%) | "
            f"{item['baseline_aligned_with_scenario']} | "
            f"{item['with_questionnaire_top_hypothesis']} ({item['with_questionnaire_top_percent']}%) | "
            f"{item['with_questionnaire_aligned_with_scenario']} | "
            f"{item['comparison_status']}"
        )
    print("")
    print(
        f"Aligned without questionnaire: {summary['aligned_without_questionnaire']}/{summary['case_count']}"
    )
    print(
        f"Aligned with questionnaire: {summary['aligned_with_questionnaire']}/{summary['case_count']}"
    )
    print(f"Improved cases: {', '.join(summary['improved_cases']) or 'none'}")
    print(f"Degraded cases: {', '.join(summary['degraded_cases']) or 'none'}")


def main() -> int:
    summary = run_campaign()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    print_report(summary)
    print("")
    print(f"JSON report saved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
