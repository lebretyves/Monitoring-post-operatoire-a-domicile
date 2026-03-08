from __future__ import annotations

import json
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import create_app


def test_patients_and_trends_endpoints() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                reading = {
                    "ts": "2026-03-04T10:00:00Z",
                    "patient_id": "PAT-001",
                    "profile": "baseline_normale",
                    "scenario": "recovery_copy_patient1",
                    "scenario_label": "Constantes Normales",
                    "hr": 82,
                    "spo2": 97,
                    "sbp": 124,
                    "dbp": 76,
                    "map": 92,
                    "rr": 16,
                    "temp": 36.9,
                    "room": "A101",
                    "battery": 99,
                    "postop_day": 1,
                    "surgery_type": "cholecystectomie laparoscopique",
                    "shock_index": 0.66,
                }
                services.state.push(reading)
                services.last_vitals["PAT-001"] = reading
                services.influx.write_vital(reading)
                services.postgres.store_alert(
                    {
                        "rule_id": "RESP_INFO",
                        "patient_id": "PAT-001",
                        "level": "INFO",
                        "status": "OPEN",
                        "title": "Desaturation moderee",
                        "message": "Alerte test sur le cas clinique actif",
                        "metric_snapshot": {
                            "scenario": "recovery_copy_patient1",
                            "scenario_label": "Constantes Normales",
                            "surgery_type": "cholecystectomie laparoscopique",
                        },
                    }
                )
                services.postgres.store_alert(
                    {
                        "rule_id": "SEPSIS_ALERT",
                        "patient_id": "PAT-001",
                        "level": "CRITICAL",
                        "status": "OPEN",
                        "title": "Sepsis suspect",
                        "message": "Alerte test hors contexte",
                        "metric_snapshot": {
                            "scenario": "sepsis_progressive",
                            "scenario_label": "Sepsis progressif",
                            "surgery_type": "chirurgie colorectale",
                        },
                    }
                )

                patients_response = client.get("/api/patients")
                assert patients_response.status_code == 200
                assert len(patients_response.json()) >= 4

                patient_response = client.get("/api/patients/PAT-001")
                assert patient_response.status_code == 200
                assert patient_response.json()["id"] == "PAT-001"

                trends_response = client.get("/api/trends/PAT-001?metric=all&hours=24")
                assert trends_response.status_code == 200
                assert trends_response.json()["patient_id"] == "PAT-001"

                ml_predict_response = client.get("/api/ml/PAT-001/predict")
                assert ml_predict_response.status_code == 200
                assert ml_predict_response.json()["patient_id"] == "PAT-001"

                llm_review_response = client.get("/api/llm/PAT-001/scenario-review")
                assert llm_review_response.status_code == 200
                assert llm_review_response.json()["source"] == "rule-based"
                assert llm_review_response.json()["scenario"] == "Constantes Normales"

                llm_package_response = client.get("/api/llm/PAT-001/clinical-package")
                assert llm_package_response.status_code == 200
                assert llm_package_response.json()["source"] == "rule-based"
                assert llm_package_response.json()["patient_id"] == "PAT-001"

                contextual_summary_response = client.post(
                    "/api/summaries/PAT-001/analyze",
                    json={
                        "patient_factors": ["Diabete", "Obesite"],
                        "perioperative_context": ["ASA >= 3"],
                        "complications_to_discuss": ["Sepsis"],
                        "free_text": "Contexte clinique declare pour test",
                    },
                )
                assert contextual_summary_response.status_code == 200
                assert contextual_summary_response.json()["clinical_context"]["patient_factors"] == [
                    "Diabete",
                    "Obesite",
                ]

                ml_feedback_response = client.post(
                    "/api/ml/PAT-001/feedback",
                    json={
                        "decision": "validate",
                        "target": "non_critical",
                        "pathology": "Constantes Normales",
                        "comment": "Temoin sain confirme",
                    },
                )
                assert ml_feedback_response.status_code == 200
                assert ml_feedback_response.json()["has_critical"] == 0

                services.postgres.store_ml_feedback(
                    patient_id="PAT-005",
                    label="validate:critical",
                    comment="Cas hors contexte",
                    pathology="Sepsis progressif",
                    surgery_type="chirurgie colorectale",
                    has_critical=1,
                )

                alerts_context_response = client.get(
                    "/api/alerts?pathology=Constantes%20Normales&surgery_type=cholecystectomie%20laparoscopique"
                )
                assert alerts_context_response.status_code == 200
                alert_rows = alerts_context_response.json()
                assert len(alert_rows) == 1
                assert alert_rows[0]["metric_snapshot"]["scenario_label"] == "Constantes Normales"
                assert alert_rows[0]["metric_snapshot"]["surgery_type"] == "cholecystectomie laparoscopique"

                feedback_list_response = client.get(
                    "/api/ml/feedback?pathology=Constantes%20Normales&surgery_type=cholecystectomie%20laparoscopique"
                )
                assert feedback_list_response.status_code == 200
                feedback_rows = feedback_list_response.json()
                assert len(feedback_rows) >= 1
                assert all(row["pathology"] == "Constantes Normales" for row in feedback_rows)
                assert all(row["surgery_type"] == "cholecystectomie laparoscopique" for row in feedback_rows)

                ml_predict_after_feedback = client.get("/api/ml/PAT-001/predict")
                assert ml_predict_after_feedback.status_code == 200
                predict_payload = ml_predict_after_feedback.json()
                assert all(
                    row["pathology"] == "Constantes Normales"
                    and row["surgery_type"] == "cholecystectomie laparoscopique"
                    for row in predict_payload["recent_feedback"]
                )

                prioritization_response = client.get("/api/llm/prioritize/patients")
                assert prioritization_response.status_code == 200
                prioritization_payload = prioritization_response.json()
                assert prioritization_payload["source"] == "rule-based"
                assert len(prioritization_payload["prioritized_patients"]) >= 1

                refresh_response = client.post("/api/patients/refresh")
                assert refresh_response.status_code == 200
                payload = refresh_response.json()
                assert payload["status"] == "requested"
                assert len(payload["assignments"]) >= 5
                assert client.get("/api/alerts?patient_id=PAT-001").json() == []
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_historical_points_seed_state_and_store_backfill_alerts() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app):
                services = app.state.services
                for second in range(0, 66, 5):
                    payload = {
                        "ts": f"2026-03-04T10:00:{second:02d}Z" if second < 60 else "2026-03-04T10:01:00Z",
                        "patient_id": "PAT-004",
                        "profile": "baseline_normale",
                        "scenario": "pulmonary_embolism",
                        "scenario_label": "Embolie pulmonaire brutale",
                        "hr": 122,
                        "spo2": 88,
                        "sbp": 108,
                        "dbp": 68,
                        "map": 81,
                        "rr": 32,
                        "temp": 37.2,
                        "room": "A104",
                        "battery": 97,
                        "postop_day": 3,
                        "surgery_type": "arthroplastie du genou",
                        "is_historical": True,
                    }
                    services.consumer._on_message(
                        None,
                        None,
                        SimpleNamespace(
                            topic="patients/PAT-004/vitals",
                            payload=json.dumps(payload).encode("utf-8"),
                        ),
                    )

                alerts = services.postgres.list_alerts(patient_id="PAT-004")
                assert len(alerts) >= 1
                assert any(alert["metric_snapshot"].get("historical_backfill") is True for alert in alerts)
                assert services.last_vitals.get("PAT-004") is None
                assert services.state.latest_snapshot("PAT-004") is not None
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir
