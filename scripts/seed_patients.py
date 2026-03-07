from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    seed_path = Path(os.getenv("PATIENTS_SEED_PATH", root / "config" / "patients_seed.json"))
    conninfo = (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'postop')} "
        f"user={os.getenv('POSTGRES_USER', 'postop')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'postop')}"
    )
    patients = json.loads(seed_path.read_text(encoding="utf-8"))
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
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
    print(f"Seeded {len(patients)} patients from {seed_path}")


if __name__ == "__main__":
    main()
