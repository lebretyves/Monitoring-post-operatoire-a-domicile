from __future__ import annotations

import os
import signal
import time
from threading import Event, Lock

from app.mqtt_client import MqttPublisher
from app.profiles import build_scenarios, load_patients, load_simulation_config
from app.scenarios import build_patient_simulators


RUNNING = True


def stop_handler(signum, frame) -> None:
    global RUNNING
    RUNNING = False


def main() -> None:
    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    config = load_simulation_config()
    patients = load_patients()
    scenarios = build_scenarios(config)
    simulators = build_patient_simulators(config, patients, scenarios)
    tick_seconds = int(os.getenv("SIMULATOR_TICK_SECONDS", str(config.get("tick_seconds", 5))))
    simulators_lock = Lock()
    refresh_event = Event()

    publisher = MqttPublisher()

    def handle_control_message(payload: dict) -> None:
        nonlocal simulators
        if payload.get("action") != "refresh_population":
            return
        assignment_map = {
            item["patient_id"]: item
            for item in payload.get("assignments", [])
            if "patient_id" in item and "scenario" in item
        }
        if not assignment_map:
            return
        with simulators_lock:
            simulators = build_patient_simulators(config, patients, scenarios, assignments=assignment_map)
        refresh_event.set()
        print("Population refreshed:")
        for simulator in simulators:
            case_label = assignment_map.get(simulator.patient.id, {}).get("case_label", simulator.patient.scenario)
            print(f"- {simulator.patient.id}: {case_label} -> {simulator.patient.scenario}")

    publisher.set_control_callback(handle_control_message)
    publisher.connect()

    print(f"Simulator started with {len(simulators)} patients and tick={tick_seconds}s")
    for simulator in simulators:
        print(f"- {simulator.patient.id}: {simulator.patient.scenario}")

    try:
        while RUNNING:
            started = time.time()
            with simulators_lock:
                current_simulators = list(simulators)
            for simulator in current_simulators:
                payload = simulator.step().to_dict()
                publisher.publish_vital(simulator.patient.id, payload)
            elapsed = time.time() - started
            wait_time = max(0.0, tick_seconds - elapsed)
            if refresh_event.wait(timeout=wait_time):
                refresh_event.clear()
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
