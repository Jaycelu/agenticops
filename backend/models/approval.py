from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class PlanVersion(Base):
    __tablename__ = "plan_version"

    id = Column(BigInteger, primary_key=True)
    remediation_plan_id = Column(BigInteger, ForeignKey("remediation_plan.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    plan_hash = Column(String(64), nullable=False, index=True)
    canonical_payload = Column(JSON, nullable=False)
    state = Column(String(30), nullable=False, index=True)
    initiated_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False)
    initiated_by_session_id = Column(String(64), nullable=False)
    frozen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    decided_at = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("remediation_plan_id", "version", name="uq_plan_version_number"),
        Index("idx_plan_version_plan_state", "remediation_plan_id", "state", "expires_at"),
    )


class ApprovalDecision(Base):
    __tablename__ = "approval_decision"

    id = Column(BigInteger, primary_key=True)
    plan_version_id = Column(BigInteger, ForeignKey("plan_version.id", ondelete="RESTRICT"), nullable=False, index=True)
    decision = Column(String(20), nullable=False, index=True)
    comment = Column(Text)
    decided_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False, index=True)
    decided_by_session_id = Column(String(64), nullable=False)
    decided_plan_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("plan_version_id", name="uq_approval_decision_plan_version"),)
