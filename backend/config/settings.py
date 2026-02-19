from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # NetBox Configuration
    netbox_url: str = "http://10.128.206.209"
    netbox_api_token: str = "487ace85b4cd9019ac8df81c41654e05a77ee031"

    # ELK Configuration
    elk_url: str = "http://10.40.29.10:8090/api/v2/search/sheets/"
    elk_username: str = "lujianzhong"
    elk_password: str = "trinasolar2025"

    # Local LLM Configuration
    llm_model_name: str = "Qwen3-32B-AWQ"
    llm_api_key: str = ""
    llm_api_url: str = "http://10.128.253.45:8000/v1"

    # Backend Configuration
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    debug: bool = True

    # Frontend Configuration
    frontend_url: str = "http://localhost:5173"

    # Database Configuration
    database_url: str = "postgresql://ljz:ljz2025@localhost:5432/netops"
    database_host: str = "localhost"
    database_port: int = 5432
    database_user: str = "ljz"
    database_password: str = "ljz2025"
    database_name: str = "netops"

    # Automation DB / Retention
    # 建议为自动化中心使用独立数据库（同一PostgreSQL实例）
    # 例如：postgresql://user:pass@localhost:5432/netops_automation
    automation_database_url: str = ""
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

    @field_validator("database_url", "automation_database_url", mode="before")
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
