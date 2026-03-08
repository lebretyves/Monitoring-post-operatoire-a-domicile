from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PostgresStorage:
    def __init__(self, conninfo: str) -> None:
        self.conninfo = conninfo

    def _conn(self):
        return psycopg.connect(self.conninfo, row_factory=dict_row)

    def close(self) -> None:
        return None

    def ensure_patients(self, seed_path: str | Path) -> None:
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

    def store_ml_feedback(
        self,
        patient_id: str,
        label: str,
        comment: str = "",
        *,
        alert_id: int | None = None,
        pathology: str | None = None,
        surgery_type: str | None = None,
        has_critical: int | None = None,
    ) -> dict[str, Any]:
        metadata = json.dumps(
            {
                "comment": comment,
                "pathology": pathology,
                "surgery_type": surgery_type,
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
        row["surgery_type"] = payload.get("surgery_type")
        row["has_critical"] = payload.get("has_critical")
        row["created_at"] = row["created_at"].isoformat()
        return row


class MemoryPostgresStorage:
    def __init__(self) -> None:
        self.patients: dict[str, dict[str, Any]] = {}
        self.alerts: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.ml_feedback: list[dict[str, Any]] = []
        self.next_alert_id = 1
        self.next_feedback_id = 1

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

    def store_ml_feedback(
        self,
        patient_id: str,
        label: str,
        comment: str = "",
        *,
        alert_id: int | None = None,
        pathology: str | None = None,
        surgery_type: str | None = None,
        has_critical: int | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": self.next_feedback_id,
            "patient_id": patient_id,
            "alert_id": alert_id,
            "label": label,
            "comment": comment,
            "pathology": pathology,
            "surgery_type": surgery_type,
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
