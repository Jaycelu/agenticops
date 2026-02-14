"""
数据库连接与会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# 创建数据库引擎
db_url = settings.automation_database_url or settings.database_url
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
        Site, DeviceState, LogSample, LogAnalysisResult,
        AutomationPolicy, AutomationTask, AutomationActionLog,
        AutomationApproval, RawAnomaly, AutomationTaskFeedback,
        AbnormalTrackerState, SSHCredential, SSHCredentialDeviceBinding,
        AssetDevice, CommandTemplate
    )
    Base.metadata.create_all(bind=engine)
