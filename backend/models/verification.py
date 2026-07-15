from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class VerificationRun(Base):
    __tablename__ = "verification_run"

    id = Column(BigInteger, primary_key=True)
    execution_job_id = Column(BigInteger, ForeignKey("execution_job.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_run_id = Column(BigInteger, ForeignKey("execution_run.id", ondelete="SET NULL"), index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    action_index = Column(Integer, nullable=False)
    policy = Column(JSON, nullable=False)
    status = Column(String(30), nullable=False, index=True)
    rounds_completed = Column(Integer, nullable=False, default=0)
    next_check_at = Column(DateTime(timezone=True), index=True)
    verdict_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    finished_at = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("execution_job_id", "action_index", name="uq_verification_run_job_action"),
        Index("idx_verification_run_due", "status", "next_check_at"),
    )


class BaselineSnapshot(Base):
    __tablename__ = "baseline_snapshot"

    id = Column(BigInteger, primary_key=True)
    verification_run_id = Column(BigInteger, ForeignKey("verification_run.id", ondelete="CASCADE"), nullable=False, index=True)
    check_id = Column(String(120), nullable=False)
    target_key = Column(String(512), nullable=False)
    value = Column(JSON, nullable=False)
    source_collected_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("verification_run_id", "check_id", name="uq_baseline_run_check"),)


class VerificationCheck(Base):
    __tablename__ = "verification_check"

    id = Column(BigInteger, primary_key=True)
    verification_run_id = Column(BigInteger, ForeignKey("verification_run.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_snapshot_id = Column(BigInteger, ForeignKey("baseline_snapshot.id", ondelete="RESTRICT"), nullable=False)
    check_id = Column(String(120), nullable=False)
    round_number = Column(Integer, nullable=False)
    verdict = Column(String(30), nullable=False, index=True)
    observed = Column(JSON, nullable=False)
    freshness_seconds = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    checked_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("verification_run_id", "check_id", "round_number", name="uq_verification_check_round"),
    )
