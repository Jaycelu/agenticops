from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_secret_key: str = ""

    # Authentication sessions. External Provider configuration is stored in the
    # database; only process-wide cookie policy lives in environment settings.
    auth_cookie_name: str = "agenticops_session"
    auth_csrf_cookie_name: str = "agenticops_csrf"
    auth_session_ttl_hours: int = 8
    auth_login_transaction_ttl_minutes: int = 10
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "lax"
    auth_public_base_url: str = ""

    # NetBox Configuration
    netbox_url: str = ""
    netbox_api_token: str = ""

    # ELK Configuration
    elk_url: str = ""
    elk_username: str = ""
    elk_password: str = ""

    # Zabbix Configuration
    zabbix_url: str = ""
    zabbix_api_url: str = ""
    zabbix_username: str = ""
    zabbix_password: str = ""

    # Local LLM Configuration
    llm_model_name: str = "Qwen/Qwen3-32B-AWQ"
    llm_api_key: str = ""
    llm_api_url: str = "http://localhost:8000/v1"

    # Phase 5: semantic memory embedding (optional).
    # Leave llm_embedding_model empty to disable semantic retrieval — the system then
    # falls back to lexical + metadata retrieval and works with zero extra dependencies.
    llm_embedding_model: str = ""
    llm_embedding_api_url: str = ""  # falls back to llm_api_url when empty

    # Backend Configuration
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    debug: bool = True
    log_level: str = "INFO"
    log_json: bool = True
    log_file_enabled: bool = False

    # Frontend Configuration
    frontend_url: str = "http://localhost:5173"

    # Database Configuration
    database_url: str = "postgresql://user:password@localhost:5432/netops_agenticops"
    database_host: str = "localhost"
    database_port: int = 5432
    database_user: str = "user"
    database_password: str = "password"
    database_name: str = "netops_agenticops"

    # Retention. All application domains share the single DATABASE_URL database;
    # isolation is enforced by schemas/tables, roles, and transaction boundaries.
    retention_raw_anomaly_days: int = 30
    retention_log_sample_days: int = 30
    retention_analysis_days: int = 60
    retention_automation_task_days: int = 90
    retention_action_log_days: int = 90
    retention_approval_days: int = 180
    retention_feedback_days: int = 180
    retention_tracker_state_days: int = 7

    # Safety guard: observe-only mode blocks non read-only automation actions
    automation_observe_only: bool = True

    # Read-only device evidence gateway. Cross-process concurrency is enforced
    # with PostgreSQL advisory locks; one device can only have one active probe.
    probe_global_concurrency: int = 20
    probe_command_timeout_seconds: int = 20
    probe_max_output_bytes: int = 262144
    approval_ttl_hours: int = 24
    idempotency_ttl_hours: int = 72
    webhook_allow_http: bool = False
    webhook_lease_seconds: int = 60
    elk_checkpoint_lease_seconds: int = 120
    elk_ingestion_page_size: int = 500
    elk_initial_lookback_hours: int = 1

    # Durable diagnostic graph defaults. These are centralized safety thresholds,
    # not agent prompt hints.
    agent_graph_lease_seconds: int = 60
    agent_graph_poll_seconds: float = 1.0
    agent_max_runs_per_case: int = 16
    agent_max_llm_calls_per_case: int = 8
    agent_max_tool_calls_per_case: int = 12
    agent_max_probe_calls_per_case: int = 10
    agent_max_replan_count: int = 3
    agent_max_runtime_seconds: int = 900
    agent_max_target_devices: int = 3
    agent_max_tool_calls_per_run: int = 3
    hypothesis_confirm_confidence: float = 0.75
    hypothesis_evidence_max_age_seconds: int = 3600
    hypothesis_max_high_weight_contradictions: int = 0

    # Ticket integration mode: local|external
    ticket_mode: str = "local"

    # External ticket system integration
    ticket_system_base_url: str = ""
    ticket_system_api_key: str = ""
    ticket_system_timeout_seconds: int = 15

    # Splunk webhook integration
    splunk_webhook_token: str = ""

    # Ansible EDA webhook integration
    eda_webhook_token: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_postgres_url(cls, value):
        if value is None:
            return value
        raw = str(value).strip()
        if raw == "":
            return raw
        if not raw.startswith("postgresql://") and not raw.startswith("postgresql+psycopg2://"):
            raise ValueError("database url must use PostgreSQL scheme: postgresql://")
        return raw

    @field_validator("auth_cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be lax, strict, or none")
        return normalized


settings = Settings()
