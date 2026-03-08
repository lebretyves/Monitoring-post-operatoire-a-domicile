from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    mqtt_host: str
    mqtt_port: int
    mqtt_qos: int
    mqtt_keepalive: int
    influx_url: str
    influx_org: str
    influx_bucket: str
    influx_token: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    backend_port: int
    frontend_origin: str
    alert_rules_path: Path
    simulation_config_path: Path
    cases_catalog_path: Path
    patients_seed_path: Path
    questionnaire_rules_path: Path
    history_default_hours: int
    enable_ml: bool
    ml_runtime_dir: Path
    enable_llm: bool
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int
    kb_root: Path
    test_mode: bool

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


def _repo_root() -> Path:
    resolved = Path(__file__).resolve()
    for parent in resolved.parents:
        if (parent / "config").exists():
            return parent
    return resolved.parents[1] if len(resolved.parents) > 1 else resolved.parent


def _resolve_path(env_name: str, relative_path: str, *, must_exist: bool = True) -> Path:
    env_value = os.getenv(env_name)
    if env_value:
        candidate = Path(env_value)
        if not must_exist or candidate.exists():
            return candidate
    return _repo_root() / relative_path


def load_settings(test_mode: bool | None = None) -> Settings:
    resolved_test_mode = _as_bool(os.getenv("APP_TEST_MODE"), False)
    if test_mode is not None:
        resolved_test_mode = test_mode
    return Settings(
        mqtt_host=os.getenv("MQTT_HOST", "localhost"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
        mqtt_qos=int(os.getenv("MQTT_QOS", "1")),
        mqtt_keepalive=int(os.getenv("MQTT_KEEPALIVE", "60")),
        influx_url=os.getenv("INFLUX_URL", "http://localhost:8086"),
        influx_org=os.getenv("INFLUX_ORG", "postop"),
        influx_bucket=os.getenv("INFLUX_BUCKET", "vitals"),
        influx_token=os.getenv("INFLUX_TOKEN", "postop-monitoring-token"),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "postop"),
        postgres_user=os.getenv("POSTGRES_USER", "postop"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "postop"),
        backend_port=int(os.getenv("BACKEND_PORT", "8000")),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        alert_rules_path=_resolve_path("ALERT_RULES_PATH", "config/alert_rules.json"),
        simulation_config_path=_resolve_path("SIMULATION_CONFIG_PATH", "config/simulation_scenarios.json"),
        cases_catalog_path=_resolve_path("CASES_CATALOG_PATH", "config/cases_catalog.json"),
        patients_seed_path=_resolve_path("PATIENTS_SEED_PATH", "config/patients_seed.json"),
        questionnaire_rules_path=_resolve_path("QUESTIONNAIRE_RULES_PATH", "config/questionnaire_rules.json"),
        history_default_hours=int(os.getenv("HISTORY_DEFAULT_HOURS", "24")),
        enable_ml=_as_bool(os.getenv("ENABLE_ML"), True),
        ml_runtime_dir=_resolve_path("ML_RUNTIME_DIR", "runtime/ml", must_exist=False),
        enable_llm=False if resolved_test_mode else _as_bool(os.getenv("ENABLE_LLM"), False),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "meditron-8b-local"),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90")),
        kb_root=_resolve_path("KB_ROOT", "kb", must_exist=False),
        test_mode=resolved_test_mode,
    )
