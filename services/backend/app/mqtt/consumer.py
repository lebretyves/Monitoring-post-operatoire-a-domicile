from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError
from typing import Any

import paho.mqtt.client as mqtt

from app.ml.features import derive_course_features
from app.mqtt.schemas import VitalPayload
from app.mqtt.topics import SIMULATOR_REFRESH_TOPIC, parse_patient_topic
from app.ws.events import alert_event, notification_event, vitals_event


class MQTTConsumer:
    def __init__(
        self,
        settings,
        state,
        influx,
        postgres,
        ml_service,
        alert_engine,
        ws_manager,
        loop: asyncio.AbstractEventLoop,
        last_vitals: dict[str, dict[str, Any]],
    ) -> None:
        self.settings = settings
        self.state = state
        self.influx = influx
        self.postgres = postgres
        self.ml_service = ml_service
        self.alert_engine = alert_engine
        self.ws_manager = ws_manager
        self.loop = loop
        self.last_vitals = last_vitals
        self.client = mqtt.Client(client_id="postop-backend-consumer")

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                client.subscribe("patients/+/vitals", qos=self.settings.mqtt_qos)

        self.client.on_connect = on_connect
        self.client.on_message = self._on_message

    def start(self) -> None:
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, self.settings.mqtt_keepalive)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish_refresh_request(self, assignments: list[dict[str, Any]]) -> None:
        payload = {"action": "refresh_population", "assignments": assignments}
        info = self.client.publish(
            SIMULATOR_REFRESH_TOPIC,
            json.dumps(payload),
            qos=self.settings.mqtt_qos,
        )
        info.wait_for_publish(timeout=5)

    def _on_message(self, client, userdata, message) -> None:
        patient_id = parse_patient_topic(message.topic)
        if not patient_id:
            return
        try:
            payload = VitalPayload.model_validate_json(message.payload)
        except (ValueError, JSONDecodeError):
            return
        reading = payload.model_dump()
        reading["patient_id"] = patient_id
        if reading.get("map") is None:
            reading["map"] = reading["dbp"] + ((reading["sbp"] - reading["dbp"]) / 3.0)
        reading["map"] = int(round(float(reading["map"])))
        reading["shock_index"] = round(reading["hr"] / max(1, reading["sbp"]), 2)
        is_historical = bool(reading.get("is_historical"))
        backfill_only = bool(reading.get("backfill_only"))
        if not backfill_only:
            self.influx.write_vital(reading)
        self.state.push(reading)
        generated_alerts = list(self.alert_engine.evaluate(reading))
        if is_historical:
            for alert in generated_alerts:
                alert["metric_snapshot"] = {
                    **alert["metric_snapshot"],
                    "is_historical": True,
                    "historical_backfill": True,
                }
                self.postgres.store_alert(alert)
            return
        history_points = self.influx.query_history(patient_id=patient_id, metric="all", hours=0)
        course_features = derive_course_features(history_points)
        self.last_vitals[patient_id] = reading
        self.ml_service.record_vital_sample(
            {
                **reading,
                "pathology": reading.get("scenario_label") or reading.get("scenario"),
                "alert_count": len(generated_alerts),
                "has_critical": int(any(alert["level"] == "CRITICAL" for alert in generated_alerts)),
                **course_features,
            }
        )
        asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast(vitals_event(reading)), self.loop)
        for alert in generated_alerts:
            stored = self.postgres.store_alert(alert)
            asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast(alert_event(stored)), self.loop)
            notification = self.postgres.store_notification(
                {
                    "patient_id": stored["patient_id"],
                    "alert_id": stored["id"],
                    "level": stored["level"],
                    "status": "UNREAD",
                    "channel": "push",
                    "title": f"{stored['level']} - {stored['title']}",
                    "message": stored["message"],
                    "payload": {
                        "rule_id": stored["rule_id"],
                        "alert_title": stored["title"],
                        "alert_message": stored["message"],
                        "status": stored["status"],
                        "metric_snapshot": stored["metric_snapshot"],
                    },
                    "created_at": stored["created_at"],
                }
            )
            asyncio.run_coroutine_threadsafe(
                self.ws_manager.broadcast(notification_event(notification)),
                self.loop,
            )
