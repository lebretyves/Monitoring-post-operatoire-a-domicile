from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.llm.validated_categories import infer_diagnosis_category, infer_surgery_category


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PostgresStorage:
    def __init__(self, conninfo: str) -> None:
        self.conninfo = conninfo

    def _conn(self):
        return psycopg.connect(self.conninfo, row_factory=dict_row)

    def _ensure_runtime_schema(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id BIGSERIAL PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                    alert_id BIGINT REFERENCES alerts(id) ON DELETE SET NULL,
                    level TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'UNREAD',
                    channel TEXT NOT NULL DEFAULT 'push',
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    read_at TIMESTAMPTZ,
                    read_by TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notifications_patient_created_at
                ON notifications (patient_id, created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notifications_status
                ON notifications (status)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL UNIQUE,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    user_agent TEXT,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_active
                ON push_subscriptions (user_id, active)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_analysis_cache (
                    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                    analysis_type TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    summary_text TEXT NOT NULL DEFAULT '',
                    questionnaire_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    analysis_state TEXT NOT NULL DEFAULT 'active',
                    anchor_vitals JSONB,
                    delta_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
                    trigger_reason TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'rule-based',
                    llm_status TEXT NOT NULL DEFAULT 'rule-based',
                    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (patient_id, analysis_type)
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_llm_analysis_cache_updated_at
                ON llm_analysis_cache (updated_at DESC)
                """
            )
            conn.commit()

    def close(self) -> None:
        return None

    def ensure_patients(self, seed_path: str | Path) -> None:
        self._ensure_runtime_schema()
        patients = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        with self._conn() as conn, conn.cursor() as cur:
            for patient in patients:
                cur.execute(
                    """
                    INSERT INTO patients (id, full_name, profile, surgery_type, postop_day, risk_level, room, history_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        profile = EXCLUDED.profile,
                        surgery_type = EXCLUDED.surgery_type,
                        postop_day = EXCLUDED.postop_day,
                        risk_level = EXCLUDED.risk_level,
                        room = EXCLUDED.room,
                        history_json = EXCLUDED.history_json
                    """,
                    (
                        patient["id"],
                        patient["full_name"],
                        patient["profile"],
                        patient["surgery_type"],
                        patient["postop_day"],
                        patient["risk_level"],
                        patient["room"],
                        json.dumps(patient.get("history", [])),
                    ),
                )
            conn.commit()

    def list_patients(self) -> list[dict[str, Any]]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, profile, surgery_type, postop_day, risk_level, room, history_json
                FROM patients
                ORDER BY id
                """
            )
            rows = cur.fetchall()
        for row in rows:
            row["history"] = row.pop("history_json")
        return rows

    def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, profile, surgery_type, postop_day, risk_level, room, history_json
                FROM patients
                WHERE id = %s
                """,
                (patient_id,),
            )
            row = cur.fetchone()
        if row:
            row["history"] = row.pop("history_json")
        return row

    def store_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        created_at = alert.get("created_at") or alert.get("metric_snapshot", {}).get("ts")
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts (rule_id, patient_id, level, status, title, message, metric_snapshot, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
                RETURNING id, rule_id, patient_id, level, status, title, message, metric_snapshot, created_at, acknowledged_at, acknowledged_by
                """,
                (
                    alert["rule_id"],
                    alert["patient_id"],
                    alert["level"],
                    alert.get("status", "OPEN"),
                    alert["title"],
                    alert["message"],
                    json.dumps(alert["metric_snapshot"]),
                    created_at,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        row["created_at"] = row["created_at"].isoformat()
        row["acknowledged_at"] = row["acknowledged_at"].isoformat() if row["acknowledged_at"] else None
        return row

    def list_alerts(
        self,
        patient_id: str | None = None,
        *,
        pathology: str | None = None,
        surgery_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, rule_id, patient_id, level, status, title, message, metric_snapshot, created_at, acknowledged_at, acknowledged_by
            FROM alerts
        """
        filters: list[str] = []
        params_list: list[Any] = []
        if patient_id:
            filters.append("patient_id = %s")
            params_list.append(patient_id)
        if pathology:
            filters.append("COALESCE(metric_snapshot->>'scenario_label', metric_snapshot->>'scenario') = %s")
            params_list.append(pathology)
        if surgery_type:
            filters.append("metric_snapshot->>'surgery_type' = %s")
            params_list.append(surgery_type)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        params: tuple[Any, ...] = tuple(params_list + [limit])
        query += " ORDER BY created_at DESC LIMIT %s"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        for row in rows:
            row["created_at"] = row["created_at"].isoformat()
            row["acknowledged_at"] = row["acknowledged_at"].isoformat() if row["acknowledged_at"] else None
        return rows

    def ack_alert(self, alert_id: int, user: str) -> dict[str, Any] | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alerts
                SET status = 'ACKNOWLEDGED',
                    acknowledged_at = NOW(),
                    acknowledged_by = %s
                WHERE id = %s
                RETURNING id, rule_id, patient_id, level, status, title, message, metric_snapshot, created_at, acknowledged_at, acknowledged_by
                """,
                (user, alert_id),
            )
            row = cur.fetchone()
            conn.commit()
        if not row:
            return None
        row["created_at"] = row["created_at"].isoformat()
        row["acknowledged_at"] = row["acknowledged_at"].isoformat() if row["acknowledged_at"] else None
        return row

    def clear_patient_alerts(self, patient_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM alerts
                WHERE patient_id = %s
                """,
                (patient_id,),
            )
            conn.commit()

    def store_notification(self, notification: dict[str, Any]) -> dict[str, Any]:
        created_at = notification.get("created_at")
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications (
                    patient_id,
                    alert_id,
                    level,
                    status,
                    channel,
                    title,
                    message,
                    payload,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
                RETURNING id, patient_id, alert_id, level, status, channel, title, message, payload, created_at, read_at, read_by
                """,
                (
                    notification["patient_id"],
                    notification.get("alert_id"),
                    notification["level"],
                    notification.get("status", "UNREAD"),
                    notification.get("channel", "push"),
                    notification["title"],
                    notification["message"],
                    json.dumps(notification.get("payload", {})),
                    created_at,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        row["created_at"] = row["created_at"].isoformat()
        row["read_at"] = row["read_at"].isoformat() if row["read_at"] else None
        return row

    def list_notifications(
        self,
        patient_id: str | None = None,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, patient_id, alert_id, level, status, channel, title, message, payload, created_at, read_at, read_by
            FROM notifications
        """
        filters: list[str] = []
        params_list: list[Any] = []
        if patient_id:
            filters.append("patient_id = %s")
            params_list.append(patient_id)
        if status:
            filters.append("status = %s")
            params_list.append(status)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        params: tuple[Any, ...] = tuple(params_list + [limit])
        query += " ORDER BY created_at DESC LIMIT %s"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        for row in rows:
            row["created_at"] = row["created_at"].isoformat()
            row["read_at"] = row["read_at"].isoformat() if row["read_at"] else None
        return rows

    def mark_notification_read(self, notification_id: int, user: str) -> dict[str, Any] | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notifications
                SET status = 'READ',
                    read_at = NOW(),
                    read_by = %s
                WHERE id = %s
                RETURNING id, patient_id, alert_id, level, status, channel, title, message, payload, created_at, read_at, read_by
                """,
                (user, notification_id),
            )
            row = cur.fetchone()
            conn.commit()
        if not row:
            return None
        row["created_at"] = row["created_at"].isoformat()
        row["read_at"] = row["read_at"].isoformat() if row["read_at"] else None
        return row

    def clear_patient_notifications(self, patient_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM notifications
                WHERE patient_id = %s
                """,
                (patient_id,),
            )
            conn.commit()

    def upsert_push_subscription(
        self,
        *,
        user_id: str,
        device_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str | None,
    ) -> dict[str, Any]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO push_subscriptions (
                    user_id,
                    device_id,
                    endpoint,
                    p256dh,
                    auth,
                    user_agent,
                    active,
                    last_seen_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
                ON CONFLICT (endpoint) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    device_id = EXCLUDED.device_id,
                    p256dh = EXCLUDED.p256dh,
                    auth = EXCLUDED.auth,
                    user_agent = EXCLUDED.user_agent,
                    active = TRUE,
                    last_seen_at = NOW()
                RETURNING id, user_id, device_id, endpoint, p256dh, auth, user_agent, active, created_at, last_seen_at
                """,
                (user_id, device_id, endpoint, p256dh, auth, user_agent),
            )
            row = cur.fetchone()
            conn.commit()
        row["created_at"] = row["created_at"].isoformat()
        row["last_seen_at"] = row["last_seen_at"].isoformat()
        return row

    def deactivate_push_subscription(self, endpoint: str) -> bool:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE push_subscriptions
                SET active = FALSE,
                    last_seen_at = NOW()
                WHERE endpoint = %s
                """,
                (endpoint,),
            )
            updated = cur.rowcount > 0
            conn.commit()
        return updated

    def list_active_push_subscriptions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT id, user_id, device_id, endpoint, p256dh, auth, user_agent, active, created_at, last_seen_at
            FROM push_subscriptions
            WHERE active = TRUE
        """
        params: tuple[Any, ...] = ()
        if user_id:
            query += " AND user_id = %s"
            params = (user_id,)
        query += " ORDER BY last_seen_at DESC"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        for row in rows:
            row["created_at"] = row["created_at"].isoformat()
            row["last_seen_at"] = row["last_seen_at"].isoformat()
        return rows

    def store_note(self, patient_id: str, content: str, note_type: str = "summary", source: str = "rule-based") -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notes (patient_id, note_type, content, source)
                VALUES (%s, %s, %s, %s)
                """,
                (patient_id, note_type, content, source),
            )
            conn.commit()

    def get_analysis_cache(self, patient_id: str, analysis_type: str) -> dict[str, Any] | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    patient_id,
                    analysis_type,
                    fingerprint,
                    payload,
                    summary_text,
                    questionnaire_json,
                    analysis_state,
                    anchor_vitals,
                    delta_signals,
                    trigger_reason,
                    source,
                    llm_status,
                    generated_at,
                    updated_at
                FROM llm_analysis_cache
                WHERE patient_id = %s AND analysis_type = %s
                """,
                (patient_id, analysis_type),
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._hydrate_analysis_cache_row(row)

    def upsert_analysis_cache(
        self,
        *,
        patient_id: str,
        analysis_type: str,
        fingerprint: str,
        payload: dict[str, Any],
        summary_text: str,
        questionnaire: dict[str, Any] | None,
        analysis_state: str,
        anchor_vitals: dict[str, Any] | None,
        delta_signals: list[str],
        trigger_reason: str,
        source: str,
        llm_status: str,
    ) -> dict[str, Any]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_analysis_cache (
                    patient_id,
                    analysis_type,
                    fingerprint,
                    payload,
                    summary_text,
                    questionnaire_json,
                    analysis_state,
                    anchor_vitals,
                    delta_signals,
                    trigger_reason,
                    source,
                    llm_status,
                    generated_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s, %s, %s, NOW(), NOW()
                )
                ON CONFLICT (patient_id, analysis_type) DO UPDATE SET
                    fingerprint = EXCLUDED.fingerprint,
                    payload = EXCLUDED.payload,
                    summary_text = EXCLUDED.summary_text,
                    questionnaire_json = EXCLUDED.questionnaire_json,
                    analysis_state = EXCLUDED.analysis_state,
                    anchor_vitals = EXCLUDED.anchor_vitals,
                    delta_signals = EXCLUDED.delta_signals,
                    trigger_reason = EXCLUDED.trigger_reason,
                    source = EXCLUDED.source,
                    llm_status = EXCLUDED.llm_status,
                    generated_at = NOW(),
                    updated_at = NOW()
                RETURNING
                    patient_id,
                    analysis_type,
                    fingerprint,
                    payload,
                    summary_text,
                    questionnaire_json,
                    analysis_state,
                    anchor_vitals,
                    delta_signals,
                    trigger_reason,
                    source,
                    llm_status,
                    generated_at,
                    updated_at
                """,
                (
                    patient_id,
                    analysis_type,
                    fingerprint,
                    json.dumps(payload),
                    summary_text,
                    json.dumps(questionnaire or {}),
                    analysis_state,
                    json.dumps(anchor_vitals) if anchor_vitals is not None else None,
                    json.dumps(delta_signals),
                    trigger_reason,
                    source,
                    llm_status,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        return self._hydrate_analysis_cache_row(row)

    def update_analysis_cache_state(
        self,
        *,
        patient_id: str,
        analysis_type: str,
        analysis_state: str,
        delta_signals: list[str],
        trigger_reason: str,
        anchor_vitals: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE llm_analysis_cache
                SET analysis_state = %s,
                    delta_signals = %s::jsonb,
                    trigger_reason = %s,
                    anchor_vitals = COALESCE(%s::jsonb, anchor_vitals),
                    updated_at = NOW()
                WHERE patient_id = %s AND analysis_type = %s
                RETURNING
                    patient_id,
                    analysis_type,
                    fingerprint,
                    payload,
                    summary_text,
                    questionnaire_json,
                    analysis_state,
                    anchor_vitals,
                    delta_signals,
                    trigger_reason,
                    source,
                    llm_status,
                    generated_at,
                    updated_at
                """,
                (
                    analysis_state,
                    json.dumps(delta_signals),
                    trigger_reason,
                    json.dumps(anchor_vitals) if anchor_vitals is not None else None,
                    patient_id,
                    analysis_type,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        if not row:
            return None
        return self._hydrate_analysis_cache_row(row)

    def clear_patient_analysis_cache(self, patient_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM llm_analysis_cache
                WHERE patient_id = %s
                """,
                (patient_id,),
            )
            conn.commit()

    def store_ml_feedback(
        self,
        patient_id: str,
        label: str,
        comment: str = "",
        *,
        alert_id: int | None = None,
        pathology: str | None = None,
        diagnosis_decision: str | None = None,
        final_diagnosis: str | None = None,
        final_diagnosis_class: str | None = None,
        surgery_type: str | None = None,
        surgery_class: str | None = None,
        has_critical: int | None = None,
    ) -> dict[str, Any]:
        diagnosis_category = final_diagnosis_class or (
            infer_diagnosis_category(final_diagnosis) if final_diagnosis else None
        )
        normalized_surgery_class = surgery_class or (
            infer_surgery_category(surgery_type) if surgery_type else None
        )
        metadata = json.dumps(
            {
                "comment": comment,
                "pathology": pathology,
                "diagnosis_decision": diagnosis_decision,
                "final_diagnosis": final_diagnosis,
                "final_diagnosis_class": diagnosis_category,
                "surgery_type": surgery_type,
                "surgery_class": normalized_surgery_class,
                "has_critical": has_critical,
            }
        )
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback_ml (patient_id, alert_id, label, comment)
                VALUES (%s, %s, %s, %s)
                RETURNING id, patient_id, alert_id, label, comment, created_at
                """,
                (patient_id, alert_id, label, metadata),
            )
            row = cur.fetchone()
            conn.commit()
        return self._hydrate_feedback_row(row)

    def list_ml_feedback(
        self,
        patient_id: str | None = None,
        *,
        pathology: str | None = None,
        surgery_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, patient_id, alert_id, label, comment, created_at
            FROM feedback_ml
        """
        params: tuple[Any, ...]
        if patient_id:
            query += " WHERE patient_id = %s"
            params = (patient_id, limit)
        else:
            params = (limit,)
        query += " ORDER BY created_at DESC LIMIT %s"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        hydrated = [self._hydrate_feedback_row(row) for row in rows]
        if pathology:
            hydrated = [row for row in hydrated if (row.get("pathology") or "").lower() == pathology.lower()]
        if surgery_type:
            hydrated = [row for row in hydrated if (row.get("surgery_type") or "").lower() == surgery_type.lower()]
        return hydrated[:limit]

    def update_patient_profile(self, patient_id: str, profile: str, risk_level: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE patients
                SET profile = %s,
                    risk_level = %s
                WHERE id = %s
                """,
                (profile, risk_level, patient_id),
            )
            conn.commit()

    def update_patient_case(self, patient_id: str, payload: dict[str, Any]) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE patients
                SET full_name = %s,
                    profile = %s,
                    surgery_type = %s,
                    postop_day = %s,
                    risk_level = %s,
                    room = %s,
                    history_json = %s::jsonb
                WHERE id = %s
                """,
                (
                    payload["full_name"],
                    payload["profile"],
                    payload["surgery_type"],
                    payload["postop_day"],
                    payload["risk_level"],
                    payload["room"],
                    json.dumps(payload.get("history", [])),
                    patient_id,
                ),
            )
            conn.commit()

    @staticmethod
    def _hydrate_feedback_row(row: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any]
        try:
            payload = json.loads(row.get("comment") or "{}")
            if not isinstance(payload, dict):
                payload = {"comment": row.get("comment", "")}
        except json.JSONDecodeError:
            payload = {"comment": row.get("comment", "")}
        row["comment"] = payload.get("comment", "")
        row["pathology"] = payload.get("pathology")
        row["diagnosis_decision"] = payload.get("diagnosis_decision")
        row["final_diagnosis"] = payload.get("final_diagnosis")
        row["final_diagnosis_class"] = payload.get("final_diagnosis_class")
        row["surgery_type"] = payload.get("surgery_type")
        row["surgery_class"] = payload.get("surgery_class")
        row["has_critical"] = payload.get("has_critical")
        row["created_at"] = row["created_at"].isoformat()
        return row

    @staticmethod
    def _hydrate_analysis_cache_row(row: dict[str, Any]) -> dict[str, Any]:
        row["generated_at"] = row["generated_at"].isoformat()
        row["updated_at"] = row["updated_at"].isoformat()
        row["questionnaire"] = row.pop("questionnaire_json") or {}
        return row


class MemoryPostgresStorage:
    def __init__(self) -> None:
        self.patients: dict[str, dict[str, Any]] = {}
        self.alerts: list[dict[str, Any]] = []
        self.notifications: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.ml_feedback: list[dict[str, Any]] = []
        self.analysis_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.push_subscriptions: list[dict[str, Any]] = []
        self.next_alert_id = 1
        self.next_notification_id = 1
        self.next_feedback_id = 1
        self.next_push_subscription_id = 1

    def close(self) -> None:
        return None

    def ensure_patients(self, seed_path: str | Path) -> None:
        payload = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        for patient in payload:
            self.patients[patient["id"]] = {
                "id": patient["id"],
                "full_name": patient["full_name"],
                "profile": patient["profile"],
                "surgery_type": patient["surgery_type"],
                "postop_day": patient["postop_day"],
                "risk_level": patient["risk_level"],
                "room": patient["room"],
                "history": patient.get("history", []),
            }

    def list_patients(self) -> list[dict[str, Any]]:
        return [self.patients[key] for key in sorted(self.patients)]

    def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        return self.patients.get(patient_id)

    def store_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": self.next_alert_id,
            "rule_id": alert["rule_id"],
            "patient_id": alert["patient_id"],
            "level": alert["level"],
            "status": alert.get("status", "OPEN"),
            "title": alert["title"],
            "message": alert["message"],
            "metric_snapshot": alert["metric_snapshot"],
            "created_at": alert.get("created_at") or alert.get("metric_snapshot", {}).get("ts") or _utc_now(),
            "acknowledged_at": None,
            "acknowledged_by": None,
        }
        self.next_alert_id += 1
        self.alerts.insert(0, row)
        return row

    def list_alerts(
        self,
        patient_id: str | None = None,
        *,
        pathology: str | None = None,
        surgery_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows = self.alerts
        if patient_id:
            rows = [row for row in rows if row["patient_id"] == patient_id]
        if pathology:
            rows = [
                row
                for row in rows
                if ((row["metric_snapshot"].get("scenario_label") or row["metric_snapshot"].get("scenario") or "").lower() == pathology.lower())
            ]
        if surgery_type:
            rows = [
                row
                for row in rows
                if (str(row["metric_snapshot"].get("surgery_type") or "").lower() == surgery_type.lower())
            ]
        return rows[:limit]

    def ack_alert(self, alert_id: int, user: str) -> dict[str, Any] | None:
        for alert in self.alerts:
            if alert["id"] == alert_id:
                alert["status"] = "ACKNOWLEDGED"
                alert["acknowledged_by"] = user
                alert["acknowledged_at"] = _utc_now()
                return alert
        return None

    def clear_patient_alerts(self, patient_id: str) -> None:
        self.alerts = [alert for alert in self.alerts if alert["patient_id"] != patient_id]

    def store_notification(self, notification: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": self.next_notification_id,
            "patient_id": notification["patient_id"],
            "alert_id": notification.get("alert_id"),
            "level": notification["level"],
            "status": notification.get("status", "UNREAD"),
            "channel": notification.get("channel", "push"),
            "title": notification["title"],
            "message": notification["message"],
            "payload": notification.get("payload", {}),
            "created_at": notification.get("created_at") or _utc_now(),
            "read_at": None,
            "read_by": None,
        }
        self.next_notification_id += 1
        self.notifications.insert(0, row)
        return row

    def list_notifications(
        self,
        patient_id: str | None = None,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows = self.notifications
        if patient_id:
            rows = [row for row in rows if row["patient_id"] == patient_id]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return rows[:limit]

    def mark_notification_read(self, notification_id: int, user: str) -> dict[str, Any] | None:
        for notification in self.notifications:
            if notification["id"] == notification_id:
                notification["status"] = "READ"
                notification["read_by"] = user
                notification["read_at"] = _utc_now()
                return notification
        return None

    def clear_patient_notifications(self, patient_id: str) -> None:
        self.notifications = [
            notification for notification in self.notifications if notification["patient_id"] != patient_id
        ]

    def upsert_push_subscription(
        self,
        *,
        user_id: str,
        device_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str | None,
    ) -> dict[str, Any]:
        now = _utc_now()
        for row in self.push_subscriptions:
            if row["endpoint"] == endpoint:
                row["user_id"] = user_id
                row["device_id"] = device_id
                row["p256dh"] = p256dh
                row["auth"] = auth
                row["user_agent"] = user_agent
                row["active"] = True
                row["last_seen_at"] = now
                return dict(row)
        created = {
            "id": self.next_push_subscription_id,
            "user_id": user_id,
            "device_id": device_id,
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent,
            "active": True,
            "created_at": now,
            "last_seen_at": now,
        }
        self.next_push_subscription_id += 1
        self.push_subscriptions.append(created)
        return dict(created)

    def deactivate_push_subscription(self, endpoint: str) -> bool:
        for row in self.push_subscriptions:
            if row["endpoint"] == endpoint:
                row["active"] = False
                row["last_seen_at"] = _utc_now()
                return True
        return False

    def list_active_push_subscriptions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        rows = [row for row in self.push_subscriptions if row.get("active")]
        if user_id:
            rows = [row for row in rows if row.get("user_id") == user_id]
        return [dict(row) for row in rows]

    def store_note(self, patient_id: str, content: str, note_type: str = "summary", source: str = "rule-based") -> None:
        self.notes.append(
            {
                "patient_id": patient_id,
                "content": content,
                "note_type": note_type,
                "source": source,
                "created_at": _utc_now(),
            }
        )

    def get_analysis_cache(self, patient_id: str, analysis_type: str) -> dict[str, Any] | None:
        row = self.analysis_cache.get((patient_id, analysis_type))
        return dict(row) if row else None

    def upsert_analysis_cache(
        self,
        *,
        patient_id: str,
        analysis_type: str,
        fingerprint: str,
        payload: dict[str, Any],
        summary_text: str,
        questionnaire: dict[str, Any] | None,
        analysis_state: str,
        anchor_vitals: dict[str, Any] | None,
        delta_signals: list[str],
        trigger_reason: str,
        source: str,
        llm_status: str,
    ) -> dict[str, Any]:
        generated_at = _utc_now()
        row = {
            "patient_id": patient_id,
            "analysis_type": analysis_type,
            "fingerprint": fingerprint,
            "payload": payload,
            "summary_text": summary_text,
            "questionnaire": questionnaire or {},
            "analysis_state": analysis_state,
            "anchor_vitals": anchor_vitals,
            "delta_signals": list(delta_signals),
            "trigger_reason": trigger_reason,
            "source": source,
            "llm_status": llm_status,
            "generated_at": generated_at,
            "updated_at": generated_at,
        }
        self.analysis_cache[(patient_id, analysis_type)] = row
        return dict(row)

    def update_analysis_cache_state(
        self,
        *,
        patient_id: str,
        analysis_type: str,
        analysis_state: str,
        delta_signals: list[str],
        trigger_reason: str,
        anchor_vitals: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        row = self.analysis_cache.get((patient_id, analysis_type))
        if not row:
            return None
        row["analysis_state"] = analysis_state
        row["delta_signals"] = list(delta_signals)
        row["trigger_reason"] = trigger_reason
        if anchor_vitals is not None:
            row["anchor_vitals"] = anchor_vitals
        row["updated_at"] = _utc_now()
        return dict(row)

    def clear_patient_analysis_cache(self, patient_id: str) -> None:
        self.analysis_cache = {
            key: value
            for key, value in self.analysis_cache.items()
            if key[0] != patient_id
        }

    def store_ml_feedback(
        self,
        patient_id: str,
        label: str,
        comment: str = "",
        *,
        alert_id: int | None = None,
        pathology: str | None = None,
        diagnosis_decision: str | None = None,
        final_diagnosis: str | None = None,
        final_diagnosis_class: str | None = None,
        surgery_type: str | None = None,
        surgery_class: str | None = None,
        has_critical: int | None = None,
    ) -> dict[str, Any]:
        diagnosis_category = final_diagnosis_class or (
            infer_diagnosis_category(final_diagnosis) if final_diagnosis else None
        )
        normalized_surgery_class = surgery_class or (
            infer_surgery_category(surgery_type) if surgery_type else None
        )
        row = {
            "id": self.next_feedback_id,
            "patient_id": patient_id,
            "alert_id": alert_id,
            "label": label,
            "comment": comment,
            "pathology": pathology,
            "diagnosis_decision": diagnosis_decision,
            "final_diagnosis": final_diagnosis,
            "final_diagnosis_class": diagnosis_category,
            "surgery_type": surgery_type,
            "surgery_class": normalized_surgery_class,
            "has_critical": has_critical,
            "created_at": _utc_now(),
        }
        self.next_feedback_id += 1
        self.ml_feedback.insert(0, row)
        return row

    def list_ml_feedback(
        self,
        patient_id: str | None = None,
        *,
        pathology: str | None = None,
        surgery_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows = self.ml_feedback
        if patient_id:
            rows = [row for row in rows if row["patient_id"] == patient_id]
        if pathology:
            rows = [row for row in rows if (row.get("pathology") or "").lower() == pathology.lower()]
        if surgery_type:
            rows = [row for row in rows if (row.get("surgery_type") or "").lower() == surgery_type.lower()]
        return rows[:limit]

    def update_patient_profile(self, patient_id: str, profile: str, risk_level: str) -> None:
        patient = self.patients.get(patient_id)
        if not patient:
            return
        patient["profile"] = profile
        patient["risk_level"] = risk_level

    def update_patient_case(self, patient_id: str, payload: dict[str, Any]) -> None:
        patient = self.patients.get(patient_id)
        if not patient:
            return
        patient["full_name"] = payload["full_name"]
        patient["profile"] = payload["profile"]
        patient["surgery_type"] = payload["surgery_type"]
        patient["postop_day"] = payload["postop_day"]
        patient["risk_level"] = payload["risk_level"]
        patient["room"] = payload["room"]
        patient["history"] = list(payload.get("history", []))
