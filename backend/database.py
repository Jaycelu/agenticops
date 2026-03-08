"""
数据库连接与会话管理
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# 统一要求生产与开发均使用 PostgreSQL，避免 SQLite 行为差异导致线上风险。
def _ensure_postgres(url: str) -> str:
    db_url = (url or "").strip()
    if not db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg2://"):
        raise RuntimeError(
            f"Unsupported database url: {db_url}. Only PostgreSQL is allowed."
        )
    return db_url

# 创建数据库引擎
db_url = _ensure_postgres(settings.automation_database_url or settings.database_url)
engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db():
    """
    获取数据库会话
    用于FastAPI依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库，创建所有表
    """
    from models.automation import (
        Site, SiteAutomationSwitch, DeviceState, LogSample, LogAnalysisResult,
        AutomationPolicy, AutomationTask, AutomationActionLog,
        AutomationApproval, RawAnomaly, AutomationTaskFeedback,
        SSHCredential, SSHCredentialDeviceBinding,
        AssetDevice, AlertEvent, LocalTicket, CommandTemplate
    )
    from models.agenticops import (
        SourceEvent, CaseRecord, EvidenceItem, AgentRun, AgentClaim,
        MemoryEntry, RemediationPlan, ExecutionRun
    )
    from models.integration_settings import IntegrationSetting
    from models.log_scope import LogScope
    active_tables = [
        Site.__table__,
        SiteAutomationSwitch.__table__,
        DeviceState.__table__,
        LogSample.__table__,
        LogAnalysisResult.__table__,
        AutomationPolicy.__table__,
        RawAnomaly.__table__,
        SSHCredential.__table__,
        SSHCredentialDeviceBinding.__table__,
        AssetDevice.__table__,
        LocalTicket.__table__,
        CommandTemplate.__table__,
        SourceEvent.__table__,
        CaseRecord.__table__,
        EvidenceItem.__table__,
        AgentRun.__table__,
        AgentClaim.__table__,
        MemoryEntry.__table__,
        RemediationPlan.__table__,
        ExecutionRun.__table__,
        IntegrationSetting.__table__,
        LogScope.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=active_tables)
    _drop_local_ticket_alert_event_fk()
    _ensure_local_ticket_source_event_column()
    _ensure_source_event_legacy_event_id_column()


def _drop_local_ticket_alert_event_fk() -> None:
    """
    退役 alert_event 前先解除 local_ticket.event_id 对旧表的外键依赖。
    """
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class rel ON rel.oid = c.conrelid
                JOIN pg_class target ON target.oid = c.confrelid
                WHERE rel.relname = 'local_ticket'
                  AND target.relname = 'alert_event'
                  AND c.contype = 'f'
                """
            )
        ).fetchall()
        for (constraint_name,) in rows:
            conn.execute(
                text(
                    f"""
                    ALTER TABLE local_ticket
                    DROP CONSTRAINT IF EXISTS "{constraint_name}"
                    """
                )
            )


def _ensure_local_ticket_source_event_column() -> None:
    """
    对历史数据库做兼容：为 local_ticket 补齐 source_event_id 列，并回填 metadata 中已有的值。
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE local_ticket
                ADD COLUMN IF NOT EXISTS source_event_id BIGINT
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE schemaname = current_schema()
                          AND indexname = 'idx_local_ticket_source_event_provider'
                    ) THEN
                        CREATE INDEX idx_local_ticket_source_event_provider
                        ON local_ticket (source_event_id, provider);
                    END IF;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE local_ticket
                SET source_event_id = NULLIF(metadata->>'source_event_id', '')::BIGINT
                WHERE source_event_id IS NULL
                  AND metadata IS NOT NULL
                  AND metadata ? 'source_event_id'
                """
            )
        )


def _ensure_source_event_legacy_event_id_column() -> None:
    """
    为事件域收口阶段补齐 source_event.legacy_event_id，并从历史 normalized_payload 回填。
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE source_event
                ADD COLUMN IF NOT EXISTS legacy_event_id BIGINT
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE schemaname = current_schema()
                          AND indexname = 'idx_source_event_legacy_event_id'
                    ) THEN
                        CREATE UNIQUE INDEX idx_source_event_legacy_event_id
                        ON source_event (legacy_event_id)
                        WHERE legacy_event_id IS NOT NULL;
                    END IF;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE source_event
                SET legacy_event_id = NULLIF(normalized_payload->>'legacy_event_id', '')::BIGINT
                WHERE legacy_event_id IS NULL
                  AND normalized_payload IS NOT NULL
                  AND normalized_payload ? 'legacy_event_id'
                """
            )
        )
