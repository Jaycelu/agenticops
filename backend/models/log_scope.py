"""
ELK 日志范围配置模型。
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from database import Base


class LogScope(Base):
    __tablename__ = "log_scope"

    id = Column(Integer, primary_key=True, index=True)
    scope_key = Column(String(80), unique=True, nullable=False, index=True)
    display_name = Column(String(120), nullable=False, index=True)
    netbox_site_id = Column(Integer, index=True)
    site_code_snapshot = Column(String(80), index=True)
    site_name_snapshot = Column(String(120), index=True)
    aliases = Column(JSON, nullable=False, default=list)
    query_filter = Column(Text, nullable=False)
    default_time_range = Column(String(64), nullable=False, default="-1d,now")
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=100)
    scope_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
