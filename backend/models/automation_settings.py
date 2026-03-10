"""
自动化设置模型。
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from database import Base


class AutomationSetting(Base):
    __tablename__ = "automation_setting"

    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(120), nullable=False)
    value = Column(JSON, nullable=False, default=dict)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())