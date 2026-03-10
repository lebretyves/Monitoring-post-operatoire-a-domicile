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
                stored_notification = services.postgres.store_notification(
                    {
                        "patient_id": "PAT-001",
                        "alert_id": 1,
                        "level": "INFO",
                        "status": "UNREAD",
                        "channel": "push",
                        "title": "INFO - Desaturation moderee",
                        "message": "Notification de test",
                        "payload": {
                            "metric_snapshot": {
                                "scenario_label": "Constantes Normales",
                                "surgery_type": "cholecystectomie laparoscopique",
                            }
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
                    "/api/llm/PAT-001/clinical-package",
                    json={
                        "patient_factors": ["Diabete", "Obesite"],
                        "perioperative_context": ["ASA >= 3"],
                        "free_text": "Contexte clinique declare pour test",
                    },
                )
                assert contextual_summary_response.status_code == 200
                assert contextual_summary_response.json()["patient_factors"] == [
                    "Diabete",
                    "Obesite",
                ]

                terrain_guidance_locked = client.post(
                    "/api/llm/PAT-001/terrain-guidance",
                    json={
                        "patient_factors": [],
                        "perioperative_context": [],
                        "free_text": "",
                    },
                )
                assert terrain_guidance_locked.status_code == 412

                ml_feedback_response = client.post(
                    "/api/ml/PAT-001/feedback",
                    json={
                        "decision": "validate",
                        "target": "non_critical",
                        "pathology": "Constantes Normales",
                        "diagnosis_decision": "validated",
                        "final_diagnosis": "Constantes post-operatoires stables",
                        "comment": "Temoin sain confirme",
                    },
                )
                assert ml_feedback_response.status_code == 200
                assert ml_feedback_response.json()["has_critical"] == 0

                terrain_guidance_ready = client.post(
                    "/api/llm/PAT-001/terrain-guidance",
                    json={
                        "patient_factors": [],
                        "perioperative_context": [],
                        "free_text": "",
                    },
                )
                assert terrain_guidance_ready.status_code == 200
                terrain_payload = terrain_guidance_ready.json()
                assert terrain_payload["patient_id"] == "PAT-001"
                assert terrain_payload["diagnosis_decision"] == "validated"
                assert terrain_payload["personalization_level"] == "low"
                assert "generaliste" in terrain_payload["warning"].lower()

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

                notifications_response = client.get("/api/notifications?patient_id=PAT-001")
                assert notifications_response.status_code == 200
                notification_rows = notifications_response.json()
                assert len(notification_rows) == 1
                assert notification_rows[0]["status"] == "UNREAD"

                mark_read_response = client.post(f"/api/notifications/{stored_notification['id']}/read")
                assert mark_read_response.status_code == 200
                assert mark_read_response.json()["status"] == "READ"

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
                assert client.get("/api/notifications?patient_id=PAT-001").json() == []
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_health_endpoints() -> None:
    """Test both lightweight and deep LLM healthcheck endpoints."""
    app = create_app(test_mode=True)
    with TestClient(app) as client:
        # Test lightweight health endpoint
        health_response = client.get("/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data["status"] == "ok"
        assert "llm" in health_data
        assert "enabled" in health_data["llm"]
        assert "service_reachable" in health_data["llm"]
        assert "model_installed" in health_data["llm"]

        # Test deep LLM health endpoint
        health_llm_response = client.get("/health/llm")
        assert health_llm_response.status_code == 200
        health_llm_data = health_llm_response.json()
        assert health_llm_data["status"] in ["healthy", "degraded"]
        assert "llm" in health_llm_data
        assert "generation_works" in health_llm_data["llm"]
        assert "fully_operational" in health_llm_data["llm"]


def test_export_pdf_contains_clinical_sections() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "respiratory_case_to_characterize",
                        "scenario_label": "Detresse respiratoire a caracteriser",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A102",
                        "battery": 96,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-05T14:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "respiratory_case_to_characterize",
                        "scenario_label": "Detresse respiratoire a caracteriser",
                        "hr": 106,
                        "spo2": 93,
                        "sbp": 118,
                        "dbp": 74,
                        "map": 89,
                        "rr": 24,
                        "temp": 38.2,
                        "room": "A102",
                        "battery": 94,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(106 / 118, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-002"] = history[-1]

                questionnaire_response = client.post(
                    "/api/llm/PAT-002/clinical-package",
                    json={
                        "questionnaire": {
                            "responder": "ide",
                            "comment": "essoufflement brutal avec douleur pleurale et mollet gonfle",
                            "answers": [
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "dyspnea_onset",
                                    "answer": "brutal",
                                },
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "chest_pain_type",
                                    "answer": "pleurale",
                                },
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "calf_pain_swelling",
                                    "answer": "yes",
                                },
                            ],
                        }
                    },
                )
                assert questionnaire_response.status_code == 200

                response = client.get("/api/export/PAT-002/pdf")
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("application/pdf")
                assert "PAT-002-report.pdf" in response.headers["content-disposition"]

                payload = response.content.decode("latin-1", errors="ignore")
                assert "Compte rendu clinique post-operatoire" in payload
                assert "Home Track" in payload
                assert "Date/heure" in payload
                assert "PAT-002" in payload
                assert "Hypotheses cliniques IA" in payload
                assert "Questionnaire differentiel" in payload
                assert "Conduite a tenir / surveillance" in payload
                assert "Impact du questionnaire differentiel" in payload
                assert "EN ATTENTE DE VALIDATION MEDICALE" in payload

                feedback_response = client.post(
                    "/api/ml/PAT-002/feedback",
                    json={
                        "decision": "validate",
                        "target": "non_critical",
                        "pathology": "Pathologie revisee",
                        "diagnosis_decision": "validated",
                        "final_diagnosis": "Etat post-operatoire stabilise",
                        "comment": "Validation et signature medecin.",
                    },
                )
                assert feedback_response.status_code == 200

                validated_response = client.get("/api/export/PAT-002/pdf")
                assert validated_response.status_code == 200
                validated_payload = validated_response.content.decode("latin-1", errors="ignore")
                assert "VALIDATION MEDICALE" in validated_payload
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


def test_clinical_package_prioritizes_cardiac_low_output_pattern() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-004",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 80,
                        "spo2": 98,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A104",
                        "battery": 96,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-04T09:00:00Z",
                        "patient_id": "PAT-004",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 96,
                        "spo2": 95,
                        "sbp": 112,
                        "dbp": 70,
                        "map": 84,
                        "rr": 19,
                        "temp": 36.9,
                        "room": "A104",
                        "battery": 95,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(96 / 112, 2),
                    },
                    {
                        "ts": "2026-03-04T10:00:00Z",
                        "patient_id": "PAT-004",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 116,
                        "spo2": 92,
                        "sbp": 94,
                        "dbp": 60,
                        "map": 71,
                        "rr": 23,
                        "temp": 36.9,
                        "room": "A104",
                        "battery": 94,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(116 / 94, 2),
                    },
                    {
                        "ts": "2026-03-04T10:30:00Z",
                        "patient_id": "PAT-004",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 122,
                        "spo2": 92,
                        "sbp": 90,
                        "dbp": 58,
                        "map": 69,
                        "rr": 24,
                        "temp": 36.9,
                        "room": "A104",
                        "battery": 93,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(122 / 90, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-004"] = history[-1]

                response = client.get("/api/llm/PAT-004/clinical-package")
                assert response.status_code == 200
                payload = response.json()
                assert payload["source"] == "rule-based"
                assert payload["hypothesis_ranking"][0]["label"] == "Complication cardiaque post-op possible"
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_clinical_package_prioritizes_progressive_pneumonia_over_ep() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "pneumonia_ira",
                        "scenario_label": "Pneumopathie ou IRA post-op progressive",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A102",
                        "battery": 96,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-04T20:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "pneumonia_ira",
                        "scenario_label": "Pneumopathie ou IRA post-op progressive",
                        "hr": 92,
                        "spo2": 95,
                        "sbp": 121,
                        "dbp": 76,
                        "map": 91,
                        "rr": 20,
                        "temp": 37.6,
                        "room": "A102",
                        "battery": 95,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(92 / 121, 2),
                    },
                    {
                        "ts": "2026-03-05T08:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "pneumonia_ira",
                        "scenario_label": "Pneumopathie ou IRA post-op progressive",
                        "hr": 106,
                        "spo2": 93,
                        "sbp": 118,
                        "dbp": 74,
                        "map": 89,
                        "rr": 24,
                        "temp": 38.2,
                        "room": "A102",
                        "battery": 94,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(106 / 118, 2),
                    },
                    {
                        "ts": "2026-03-05T14:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "pneumonia_ira",
                        "scenario_label": "Pneumopathie ou IRA post-op progressive",
                        "hr": 114,
                        "spo2": 90,
                        "sbp": 114,
                        "dbp": 72,
                        "map": 86,
                        "rr": 28,
                        "temp": 38.6,
                        "room": "A102",
                        "battery": 93,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(114 / 114, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-002"] = history[-1]

                response = client.get("/api/llm/PAT-002/clinical-package")
                assert response.status_code == 200
                payload = response.json()
                assert payload["source"] == "rule-based"
                assert payload["hypothesis_ranking"][0]["label"] == "Complication respiratoire post-op (pneumopathie / IRA)"
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_clinical_package_reranks_from_questionnaire_clues() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "respiratory_case_to_characterize",
                        "scenario_label": "Detresse respiratoire a caracteriser",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A102",
                        "battery": 96,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-04T12:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "respiratory_case_to_characterize",
                        "scenario_label": "Detresse respiratoire a caracteriser",
                        "hr": 84,
                        "spo2": 95,
                        "sbp": 122,
                        "dbp": 76,
                        "map": 91,
                        "rr": 18,
                        "temp": 36.8,
                        "room": "A102",
                        "battery": 95,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(84 / 122, 2),
                    },
                    {
                        "ts": "2026-03-04T16:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "respiratory_case_to_characterize",
                        "scenario_label": "Detresse respiratoire a caracteriser",
                        "hr": 92,
                        "spo2": 94,
                        "sbp": 120,
                        "dbp": 74,
                        "map": 89,
                        "rr": 21,
                        "temp": 36.9,
                        "room": "A102",
                        "battery": 94,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(92 / 120, 2),
                    },
                    {
                        "ts": "2026-03-04T19:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "respiratory_case_to_characterize",
                        "scenario_label": "Detresse respiratoire a caracteriser",
                        "hr": 106,
                        "spo2": 93,
                        "sbp": 118,
                        "dbp": 72,
                        "map": 88,
                        "rr": 24,
                        "temp": 36.9,
                        "room": "A102",
                        "battery": 93,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(106 / 118, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-002"] = history[-1]

                baseline_response = client.get("/api/llm/PAT-002/clinical-package")
                assert baseline_response.status_code == 200
                baseline_payload = baseline_response.json()
                assert baseline_payload["source"] == "rule-based"
                assert (
                    baseline_payload["hypothesis_ranking"][0]["label"]
                    == "Complication respiratoire post-op (pneumopathie / IRA)"
                )
                assert sum(row["compatibility_percent"] for row in baseline_payload["hypothesis_ranking"]) == 100

                questionnaire_response = client.post(
                    "/api/llm/PAT-002/clinical-package",
                    json={
                        "questionnaire": {
                            "responder": "ide",
                            "comment": "essoufflement brutal avec douleur pleurale et mollet gonfle",
                            "answers": [
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "dyspnea_onset",
                                    "answer": "brutal",
                                },
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "chest_pain_type",
                                    "answer": "pleurale",
                                },
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "cough",
                                    "answer": "no",
                                },
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "sputum",
                                    "answer": "none",
                                },
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "calf_pain_swelling",
                                    "answer": "yes",
                                },
                            ],
                        }
                    },
                )
                assert questionnaire_response.status_code == 200
                questionnaire_payload = questionnaire_response.json()
                assert questionnaire_payload["source"] == "rule-based"
                assert questionnaire_payload["hypothesis_ranking"][0]["label"] == "Embolie pulmonaire possible"
                assert questionnaire_payload["hypothesis_ranking"][0]["compatibility_percent"] > 40
                assert (
                    questionnaire_payload["questionnaire_baseline_hypothesis_ranking"][0]["label"]
                    == baseline_payload["hypothesis_ranking"][0]["label"]
                )
                assert sum(row["compatibility_percent"] for row in questionnaire_payload["hypothesis_ranking"]) == 100
                assert "questionnaire differentiel" in questionnaire_payload["structured_synthesis"].lower()

                cached_questionnaire_response = client.get("/api/llm/PAT-002/clinical-package")
                assert cached_questionnaire_response.status_code == 200
                cached_questionnaire_payload = cached_questionnaire_response.json()
                assert (
                    cached_questionnaire_payload["questionnaire_baseline_hypothesis_ranking"][0]["label"]
                    == baseline_payload["hypothesis_ranking"][0]["label"]
                )
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_clinical_package_cache_and_resting_state_persist() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "pneumonia_ira",
                        "scenario_label": "Pneumopathie ou IRA post-op progressive",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A102",
                        "battery": 96,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-05T14:00:00Z",
                        "patient_id": "PAT-002",
                        "profile": "baseline_normale",
                        "scenario": "pneumonia_ira",
                        "scenario_label": "Pneumopathie ou IRA post-op progressive",
                        "hr": 106,
                        "spo2": 93,
                        "sbp": 118,
                        "dbp": 74,
                        "map": 89,
                        "rr": 24,
                        "temp": 38.2,
                        "room": "A102",
                        "battery": 94,
                        "postop_day": 2,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(106 / 118, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-002"] = history[-1]

                first_response = client.get("/api/llm/PAT-002/clinical-package")
                assert first_response.status_code == 200
                first_payload = first_response.json()
                assert first_payload["analysis_state"]["cache_status"] == "fresh"
                assert first_payload["summary_text"]
                assert first_payload["explanatory_score"]["score"] >= 0

                second_response = client.get("/api/llm/PAT-002/clinical-package")
                assert second_response.status_code == 200
                second_payload = second_response.json()
                assert second_payload["analysis_state"]["cache_status"] == "cached"
                assert second_payload["summary_text"] == first_payload["summary_text"]

                questionnaire_response = client.post(
                    "/api/llm/PAT-002/clinical-package",
                    json={
                        "questionnaire": {
                            "responder": "patient",
                            "comment": "Essoufflement brutal",
                            "answers": [
                                {
                                    "module_id": "respiratory_differential",
                                    "question_id": "dyspnea_onset",
                                    "answer": "brutal",
                                }
                            ],
                        }
                    },
                )
                assert questionnaire_response.status_code == 200
                resting_payload = questionnaire_response.json()
                assert resting_payload["analysis_state"]["mode"] == "resting"
                assert resting_payload["questionnaire_state"]["answers"][0]["answer"] == "brutal"
                assert resting_payload["questionnaire_baseline_hypothesis_ranking"]

                updated_reading = {
                    **history[-1],
                    "ts": "2026-03-05T15:00:00Z",
                    "hr": 120,
                    "map": 80,
                    "rr": 28,
                    "shock_index": round(120 / 118, 2),
                }
                services.state.push(updated_reading)
                services.influx.write_vital(updated_reading)
                services.last_vitals["PAT-002"] = updated_reading

                stale_response = client.get("/api/llm/PAT-002/clinical-package")
                assert stale_response.status_code == 200
                stale_payload = stale_response.json()
                assert stale_payload["analysis_state"]["mode"] == "stale"
                assert stale_payload["analysis_state"]["cache_status"] == "stale"
                assert stale_payload["analysis_state"]["delta_signals"]
                assert stale_payload["questionnaire_baseline_hypothesis_ranking"]
                assert stale_payload["summary_text"] == resting_payload["summary_text"]
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_questionnaire_selects_subtle_hemodynamic_and_infectious_modules() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services

                low_grade_bleed_history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "values": {"hr": 75, "spo2": 98, "rr": 15, "temp": 36.8, "map": 92, "shock_index": round(75 / 123, 2)},
                    },
                    {
                        "ts": "2026-03-05T08:00:00Z",
                        "values": {"hr": 82, "spo2": 98, "rr": 16, "temp": 36.8, "map": 89, "shock_index": round(82 / 119, 2)},
                    },
                    {
                        "ts": "2026-03-05T14:00:00Z",
                        "values": {"hr": 88, "spo2": 97, "rr": 17, "temp": 36.7, "map": 86, "shock_index": round(88 / 114, 2)},
                    },
                    {
                        "ts": "2026-03-05T20:00:00Z",
                        "values": {"hr": 94, "spo2": 97, "rr": 18, "temp": 36.7, "map": 83, "shock_index": round(94 / 110, 2)},
                    },
                ]
                hemodynamic_selection = services.questionnaire_engine.select_modules(
                    last_vitals={
                        "hr": 94,
                        "spo2": 97,
                        "rr": 18,
                        "temp": 36.7,
                        "map": 83,
                        "shock_index": round(94 / 110, 2),
                    },
                    alerts=[],
                    history_points=low_grade_bleed_history,
                )
                assert {module["id"] for module in hemodynamic_selection.modules} == {"hemodynamic_differential"}

                subtle_sepsis_history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "values": {"hr": 79, "spo2": 97, "rr": 16, "temp": 36.9, "map": 91, "shock_index": round(79 / 123, 2)},
                    },
                    {
                        "ts": "2026-03-05T08:00:00Z",
                        "values": {"hr": 86, "spo2": 97, "rr": 18, "temp": 37.2, "map": 89, "shock_index": round(86 / 122, 2)},
                    },
                    {
                        "ts": "2026-03-05T16:00:00Z",
                        "values": {"hr": 92, "spo2": 96, "rr": 20, "temp": 37.6, "map": 86, "shock_index": round(92 / 118, 2)},
                    },
                    {
                        "ts": "2026-03-05T22:00:00Z",
                        "values": {"hr": 98, "spo2": 96, "rr": 21, "temp": 37.8, "map": 82, "shock_index": round(98 / 114, 2)},
                    },
                ]
                infectious_selection = services.questionnaire_engine.select_modules(
                    last_vitals={
                        "hr": 98,
                        "spo2": 96,
                        "rr": 21,
                        "temp": 37.8,
                        "map": 82,
                        "shock_index": round(98 / 114, 2),
                    },
                    alerts=[],
                    history_points=subtle_sepsis_history,
                )
                selected_module_ids = {module["id"] for module in infectious_selection.modules}
                assert "infectious_differential" in selected_module_ids
                assert "pain_differential" not in selected_module_ids
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_clinical_package_prioritizes_hemorrhage_over_cardiac_when_hypovolemic() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-003",
                        "profile": "baseline_normale",
                        "scenario": "hemorrhage_j2",
                        "scenario_label": "Hemorragie brutale J+2",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A103",
                        "battery": 96,
                        "postop_day": 2,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-05T06:00:00Z",
                        "patient_id": "PAT-003",
                        "profile": "baseline_normale",
                        "scenario": "hemorrhage_j2",
                        "scenario_label": "Hemorragie brutale J+2",
                        "hr": 92,
                        "spo2": 97,
                        "sbp": 116,
                        "dbp": 74,
                        "map": 88,
                        "rr": 18,
                        "temp": 36.8,
                        "room": "A103",
                        "battery": 95,
                        "postop_day": 2,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(92 / 116, 2),
                    },
                    {
                        "ts": "2026-03-05T07:00:00Z",
                        "patient_id": "PAT-003",
                        "profile": "baseline_normale",
                        "scenario": "hemorrhage_j2",
                        "scenario_label": "Hemorragie brutale J+2",
                        "hr": 112,
                        "spo2": 96,
                        "sbp": 98,
                        "dbp": 66,
                        "map": 77,
                        "rr": 20,
                        "temp": 36.7,
                        "room": "A103",
                        "battery": 94,
                        "postop_day": 2,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(112 / 98, 2),
                    },
                    {
                        "ts": "2026-03-05T07:20:00Z",
                        "patient_id": "PAT-003",
                        "profile": "baseline_normale",
                        "scenario": "hemorrhage_j2",
                        "scenario_label": "Hemorragie brutale J+2",
                        "hr": 128,
                        "spo2": 96,
                        "sbp": 84,
                        "dbp": 56,
                        "map": 65,
                        "rr": 22,
                        "temp": 36.7,
                        "room": "A103",
                        "battery": 93,
                        "postop_day": 2,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(128 / 84, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-003"] = history[-1]

                response = client.get("/api/llm/PAT-003/clinical-package")
                assert response.status_code == 200
                payload = response.json()
                assert payload["source"] == "rule-based"
                assert payload["hypothesis_ranking"][0]["label"] == "Hemorragie / hypovolemie possible"
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_clinical_package_prioritizes_progressive_sepsis_over_pneumonia_when_hemodynamics_drop() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-005",
                        "profile": "baseline_normale",
                        "scenario": "sepsis_progressive",
                        "scenario_label": "Sepsis progressif",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A105",
                        "battery": 96,
                        "postop_day": 3,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-05T08:00:00Z",
                        "patient_id": "PAT-005",
                        "profile": "baseline_normale",
                        "scenario": "sepsis_progressive",
                        "scenario_label": "Sepsis progressif",
                        "hr": 96,
                        "spo2": 96,
                        "sbp": 118,
                        "dbp": 72,
                        "map": 87,
                        "rr": 20,
                        "temp": 37.9,
                        "room": "A105",
                        "battery": 95,
                        "postop_day": 3,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(96 / 118, 2),
                    },
                    {
                        "ts": "2026-03-05T16:00:00Z",
                        "patient_id": "PAT-005",
                        "profile": "baseline_normale",
                        "scenario": "sepsis_progressive",
                        "scenario_label": "Sepsis progressif",
                        "hr": 112,
                        "spo2": 94,
                        "sbp": 106,
                        "dbp": 62,
                        "map": 77,
                        "rr": 24,
                        "temp": 38.7,
                        "room": "A105",
                        "battery": 94,
                        "postop_day": 3,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(112 / 106, 2),
                    },
                    {
                        "ts": "2026-03-05T22:00:00Z",
                        "patient_id": "PAT-005",
                        "profile": "baseline_normale",
                        "scenario": "sepsis_progressive",
                        "scenario_label": "Sepsis progressif",
                        "hr": 124,
                        "spo2": 93,
                        "sbp": 94,
                        "dbp": 56,
                        "map": 69,
                        "rr": 26,
                        "temp": 39.1,
                        "room": "A105",
                        "battery": 93,
                        "postop_day": 3,
                        "surgery_type": "chirurgie colorectale",
                        "shock_index": round(124 / 94, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-005"] = history[-1]

                response = client.get("/api/llm/PAT-005/clinical-package")
                assert response.status_code == 200
                payload = response.json()
                assert payload["source"] == "rule-based"
                assert payload["hypothesis_ranking"][0]["label"] == "Sepsis / complication infectieuse possible"
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_clinical_package_prioritizes_pain_when_fluctuating_without_infectious_or_respiratory_signals() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                services.postgres.patients["PAT-006"] = {
                    "id": "PAT-006",
                    "full_name": "PAT-006",
                    "profile": "baseline_normale",
                    "surgery_type": "chirurgie thoracique",
                    "postop_day": 1,
                    "risk_level": "surveillance_postop",
                    "room": "A106",
                    "history": [],
                }
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-006",
                        "profile": "baseline_normale",
                        "scenario": "pain_postop_uncontrolled",
                        "scenario_label": "Douleur post-op non controlee",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A106",
                        "battery": 96,
                        "postop_day": 1,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-04T10:00:00Z",
                        "patient_id": "PAT-006",
                        "profile": "baseline_normale",
                        "scenario": "pain_postop_uncontrolled",
                        "scenario_label": "Douleur post-op non controlee",
                        "hr": 108,
                        "spo2": 97,
                        "sbp": 138,
                        "dbp": 86,
                        "map": 103,
                        "rr": 22,
                        "temp": 36.9,
                        "room": "A106",
                        "battery": 95,
                        "postop_day": 1,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(108 / 138, 2),
                    },
                    {
                        "ts": "2026-03-04T13:00:00Z",
                        "patient_id": "PAT-006",
                        "profile": "baseline_normale",
                        "scenario": "pain_postop_uncontrolled",
                        "scenario_label": "Douleur post-op non controlee",
                        "hr": 88,
                        "spo2": 98,
                        "sbp": 126,
                        "dbp": 79,
                        "map": 95,
                        "rr": 17,
                        "temp": 36.8,
                        "room": "A106",
                        "battery": 94,
                        "postop_day": 1,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(88 / 126, 2),
                    },
                    {
                        "ts": "2026-03-04T18:00:00Z",
                        "patient_id": "PAT-006",
                        "profile": "baseline_normale",
                        "scenario": "pain_postop_uncontrolled",
                        "scenario_label": "Douleur post-op non controlee",
                        "hr": 112,
                        "spo2": 96,
                        "sbp": 136,
                        "dbp": 84,
                        "map": 101,
                        "rr": 22,
                        "temp": 36.9,
                        "room": "A106",
                        "battery": 93,
                        "postop_day": 1,
                        "surgery_type": "chirurgie thoracique",
                        "shock_index": round(112 / 136, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-006"] = history[-1]

                response = client.get("/api/llm/PAT-006/clinical-package")
                assert response.status_code == 200
                payload = response.json()
                assert payload["source"] == "rule-based"
                assert payload["hypothesis_ranking"][0]["label"] == "Douleur post-op non controlee possible"
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir


def test_clinical_package_prioritizes_abrupt_cardiac_low_output_over_ep_when_respiratory_burden_is_moderate() -> None:
    previous_runtime_dir = os.environ.get("ML_RUNTIME_DIR")
    try:
        with TemporaryDirectory() as runtime_dir:
            os.environ["ML_RUNTIME_DIR"] = runtime_dir
            app = create_app(test_mode=True)
            with TestClient(app) as client:
                services = client.app.state.services
                services.postgres.patients["PAT-007"] = {
                    "id": "PAT-007",
                    "full_name": "PAT-007",
                    "profile": "baseline_normale",
                    "surgery_type": "chirurgie vasculaire majeure",
                    "postop_day": 2,
                    "risk_level": "surveillance_postop",
                    "room": "A107",
                    "history": [],
                }
                history = [
                    {
                        "ts": "2026-03-04T08:00:00Z",
                        "patient_id": "PAT-007",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 80,
                        "spo2": 97,
                        "sbp": 124,
                        "dbp": 78,
                        "map": 93,
                        "rr": 16,
                        "temp": 36.8,
                        "room": "A107",
                        "battery": 96,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(80 / 124, 2),
                    },
                    {
                        "ts": "2026-03-05T14:00:00Z",
                        "patient_id": "PAT-007",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 82,
                        "spo2": 97,
                        "sbp": 122,
                        "dbp": 76,
                        "map": 91,
                        "rr": 17,
                        "temp": 36.8,
                        "room": "A107",
                        "battery": 95,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(82 / 122, 2),
                    },
                    {
                        "ts": "2026-03-05T14:20:00Z",
                        "patient_id": "PAT-007",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 118,
                        "spo2": 94,
                        "sbp": 92,
                        "dbp": 60,
                        "map": 71,
                        "rr": 22,
                        "temp": 36.8,
                        "room": "A107",
                        "battery": 94,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(118 / 92, 2),
                    },
                    {
                        "ts": "2026-03-05T14:35:00Z",
                        "patient_id": "PAT-007",
                        "profile": "baseline_normale",
                        "scenario": "cardiac_postop_complication",
                        "scenario_label": "Complication cardiaque post-op rapide",
                        "hr": 126,
                        "spo2": 93,
                        "sbp": 86,
                        "dbp": 56,
                        "map": 66,
                        "rr": 24,
                        "temp": 36.8,
                        "room": "A107",
                        "battery": 93,
                        "postop_day": 2,
                        "surgery_type": "chirurgie vasculaire majeure",
                        "shock_index": round(126 / 86, 2),
                    },
                ]
                for reading in history:
                    services.state.push(reading)
                    services.influx.write_vital(reading)
                services.last_vitals["PAT-007"] = history[-1]

                response = client.get("/api/llm/PAT-007/clinical-package")
                assert response.status_code == 200
                payload = response.json()
                assert payload["source"] == "rule-based"
                assert payload["hypothesis_ranking"][0]["label"] == "Complication cardiaque post-op possible"
    finally:
        if previous_runtime_dir is None:
            os.environ.pop("ML_RUNTIME_DIR", None)
        else:
            os.environ["ML_RUNTIME_DIR"] = previous_runtime_dir
