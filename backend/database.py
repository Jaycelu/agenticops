"""
数据库连接与会话管理
"""
from sqlalchemy import create_engine
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
    Base.metadata.create_all(bind=engine)
