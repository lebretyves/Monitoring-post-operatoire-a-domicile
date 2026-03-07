from __future__ import annotations

import re


SIMULATOR_REFRESH_TOPIC = "simulator/control/refresh"
TOPIC_RE = re.compile(r"^patients/(?P<patient_id>[^/]+)/vitals$")


def parse_patient_topic(topic: str) -> str | None:
    match = TOPIC_RE.match(topic)
    if not match:
        return None
    return match.group("patient_id")
