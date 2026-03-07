from __future__ import annotations

import json
import os
from threading import Event

import paho.mqtt.client as mqtt


class MqttPublisher:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "localhost")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.keepalive = int(os.getenv("MQTT_KEEPALIVE", "60"))
        self.qos = int(os.getenv("MQTT_QOS", "1"))
        self.topic_template = "patients/{patient_id}/vitals"
        self.control_topic = "simulator/control/refresh"
        self.client = mqtt.Client(client_id="postop-simulator")
        self.connected = Event()
        self.control_callback = None

        username = os.getenv("MQTT_USERNAME", "")
        password = os.getenv("MQTT_PASSWORD", "")
        if username:
            self.client.username_pw_set(username, password)

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                client.subscribe(self.control_topic, qos=self.qos)
                self.connected.set()

        self.client.on_connect = on_connect
        self.client.on_message = self._on_message

    def connect(self) -> None:
        self.client.connect(self.host, self.port, self.keepalive)
        self.client.loop_start()
        self.connected.wait(timeout=10)

    def publish_vital(self, patient_id: str, payload: dict) -> None:
        topic = self.topic_template.format(patient_id=patient_id)
        self.client.publish(topic, json.dumps(payload), qos=self.qos)

    def set_control_callback(self, callback) -> None:
        self.control_callback = callback

    def _on_message(self, client, userdata, message) -> None:
        if message.topic != self.control_topic or not self.control_callback:
            return
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except json.JSONDecodeError:
            return
        self.control_callback(payload)

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
