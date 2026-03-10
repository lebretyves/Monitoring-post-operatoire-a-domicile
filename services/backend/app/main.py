from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.alerting.engine import AlertEngine
from app.alerting.rules_loader import load_rules
from app.alerting.state import AlertState
from app.llm.client import OllamaClient
from app.llm.kb import LocalKnowledgeBase
from app.llm.questionnaire import QuestionnaireEngine
from app.ml.anomaly import AnomalyService
from app.ml.criticity_service import CriticityMLService
from app.mqtt.consumer import MQTTConsumer
from app.routers import alerts, export, llm, ml, notifications, patients, trends
from app.routers.push import router as push_router
from app.services.webpush import WebPushService
from app.routers.patients import _build_refresh_assignments, _default_monitoring_level
from app.settings import load_settings
from app.storage.influx import InfluxStorage, MemoryInfluxStorage
from app.storage.postgres import MemoryPostgresStorage, PostgresStorage
from app.ws.manager import WebSocketManager


def create_app(test_mode: bool | None = None) -> FastAPI:
    settings = load_settings(test_mode=test_mode)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()
        state = AlertState()
        last_vitals: dict[str, dict] = {}
        postgres = MemoryPostgresStorage() if settings.test_mode else PostgresStorage(settings.postgres_dsn)
        influx = (
            MemoryInfluxStorage()
            if settings.test_mode
            else InfluxStorage(
                url=settings.influx_url,
                token=settings.influx_token,
                org=settings.influx_org,
                bucket=settings.influx_bucket,
            )
        )
        postgres.ensure_patients(settings.patients_seed_path)
        ws_manager = WebSocketManager()
        alert_engine = AlertEngine(load_rules(settings.alert_rules_path), state=state)
        anomaly_service = AnomalyService(enabled=settings.enable_ml)
        ml_service = CriticityMLService(settings.ml_runtime_dir)
        llm_client = OllamaClient(
            enabled=settings.enable_llm,
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
        knowledge_base = LocalKnowledgeBase(settings.kb_root)
        questionnaire_engine = QuestionnaireEngine(settings.questionnaire_rules_path)
        webpush_service = WebPushService(settings=settings, postgres=postgres)
        consumer = MQTTConsumer(
            settings=settings,
            state=state,
            influx=influx,
            postgres=postgres,
            ml_service=ml_service,
            alert_engine=alert_engine,
            ws_manager=ws_manager,
            webpush_service=webpush_service,
            loop=loop,
            last_vitals=last_vitals,
        )
        app.state.services = SimpleNamespace(
            settings=settings,
            state=state,
            last_vitals=last_vitals,
            postgres=postgres,
            influx=influx,
            alert_engine=alert_engine,
            ws_manager=ws_manager,
            anomaly_service=anomaly_service,
            ml_service=ml_service,
            llm_client=llm_client,
            knowledge_base=knowledge_base,
            questionnaire_engine=questionnaire_engine,
            webpush_service=webpush_service,
            consumer=consumer,
        )
        if not settings.test_mode:
            consumer.start()
            await asyncio.sleep(1)
            patient_ids = [patient["id"] for patient in postgres.list_patients()]
            if patient_ids:
                assignments = _build_refresh_assignments(
                    settings.simulation_config_path,
                    settings.cases_catalog_path,
                    patient_ids,
                )
                for patient_id in patient_ids:
                    influx.clear_patient_history(patient_id)
                    postgres.clear_patient_alerts(patient_id)
                    postgres.clear_patient_notifications(patient_id)
                    postgres.clear_patient_analysis_cache(patient_id)
                    state.clear_patient(patient_id)
                    last_vitals.pop(patient_id, None)
                consumer.publish_refresh_request(assignments)
                for assignment in assignments:
                    postgres.update_patient_case(
                        patient_id=str(assignment["patient_id"]),
                        payload={
                            "full_name": assignment["full_name"],
                            "profile": assignment["profile"],
                            "surgery_type": assignment["surgery_type"],
                            "postop_day": assignment["postop_day"],
                            "risk_level": assignment.get("risk_level", _default_monitoring_level()),
                            "room": assignment["room"],
                            "history": assignment.get("history", []),
                        },
                    )
        try:
            yield
        finally:
            if not settings.test_mode:
                consumer.stop()
            influx.close()
            postgres.close()

    app = FastAPI(title="Postop Monitoring API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(patients.router)
    app.include_router(alerts.router)
    app.include_router(trends.router)
    app.include_router(export.router)
    app.include_router(ml.router)
    app.include_router(llm.router)
    app.include_router(notifications.router)
    app.include_router(push_router)

    @app.get("/")
    def root():
        return {"service": "postop-monitoring-backend", "status": "ok"}

    @app.get("/health")
    async def health():
        llm_service_reachable = await app.state.services.llm_client.is_available(timeout_seconds=2)
        llm_model_installed = await app.state.services.llm_client.is_model_installed(timeout_seconds=2)
        return {
            "status": "ok",
            "test_mode": settings.test_mode,
            "llm": {
                "enabled": settings.enable_llm,
                "model": settings.ollama_model,
                "base_url": settings.ollama_base_url,
                "reachable": llm_service_reachable and llm_model_installed,
                "service_reachable": llm_service_reachable,
                "model_installed": llm_model_installed,
            },
        }

    @app.get("/health/llm")
    async def health_llm():
        """
        Healthcheck approfondi du LLM : vérifie qu'une génération réelle fonctionne.
        Plus lent que /health, mais détecte les problèmes de cold start, timeout, et génération.
        """
        llm_service_reachable = await app.state.services.llm_client.is_available(timeout_seconds=2)
        llm_model_installed = await app.state.services.llm_client.is_model_installed(timeout_seconds=2)
        llm_generation_works = await app.state.services.llm_client.probe_generation(timeout_seconds=12)
        
        overall_status = "healthy" if (llm_service_reachable and llm_model_installed and llm_generation_works) else "degraded"
        
        return {
            "status": overall_status,
            "llm": {
                "enabled": settings.enable_llm,
                "model": settings.ollama_model,
                "base_url": settings.ollama_base_url,
                "service_reachable": llm_service_reachable,
                "model_installed": llm_model_installed,
                "generation_works": llm_generation_works,
                "fully_operational": llm_service_reachable and llm_model_installed and llm_generation_works,
            },
        }

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket):
        manager = app.state.services.ws_manager
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


app = create_app()
