CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    profile TEXT NOT NULL,
    surgery_type TEXT NOT NULL,
    postop_day INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL,
    room TEXT NOT NULL,
    history_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    rule_id TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    metric_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_patient_created_at ON alerts (patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);

CREATE TABLE IF NOT EXISTS notes (
    id BIGSERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    note_type TEXT NOT NULL DEFAULT 'summary',
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'rule-based',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
);

CREATE INDEX IF NOT EXISTS idx_llm_analysis_cache_updated_at ON llm_analysis_cache (updated_at DESC);

CREATE TABLE IF NOT EXISTS feedback_ml (
    id BIGSERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    alert_id BIGINT REFERENCES alerts(id) ON DELETE SET NULL,
    label TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
);

CREATE INDEX IF NOT EXISTS idx_notifications_patient_created_at ON notifications (patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications (status);
