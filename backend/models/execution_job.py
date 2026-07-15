from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.sql import func

from database import Base


class ExecutionJob(Base):
    __tablename__ = "execution_job"

    id = Column(BigInteger, primary_key=True)
    plan_version_id = Column(BigInteger, ForeignKey("plan_version.id", ondelete="RESTRICT"), nullable=False)
    remediation_plan_id = Column(BigInteger, ForeignKey("remediation_plan.id", ondelete="RESTRICT"), nullable=False, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_hash = Column(String(64), nullable=False)
    idempotency_key = Column(String(160), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    requested_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False)
    requested_by_session_id = Column(String(64), nullable=False)
    result = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    error_code = Column(String(80))
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("plan_version_id", name="uq_execution_job_plan_version"),
        UniqueConstraint("idempotency_key", name="uq_execution_job_idempotency_key"),
    )


class ExecutionActionResult(Base):
    __tablename__ = "execution_action_result"

    id = Column(BigInteger, primary_key=True)
    execution_job_id = Column(BigInteger, ForeignKey("execution_job.id", ondelete="CASCADE"), nullable=False, index=True)
    action_index = Column(Integer, nullable=False)
    tool_id = Column(String(120), nullable=False)
    capability = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    request_hash = Column(String(64), nullable=False)
    result = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("execution_job_id", "action_index", name="uq_execution_action_index"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"

    id = Column(BigInteger, primary_key=True)
    scope = Column(String(80), nullable=False)
    idempotency_key = Column(String(160), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    resource_type = Column(String(80))
    resource_id = Column(String(120))
    response_snapshot = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),)
