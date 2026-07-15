from __future__ import annotations

from sqlalchemy import Column, DateTime, JSON, String, text
from sqlalchemy.sql import func

from database import Base


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"

    worker_name = Column(String(120), primary_key=True)
    status = Column(String(30), nullable=False)
    details = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
