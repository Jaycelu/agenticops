"""
AgenticOps 核心数据模型。
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, DateTime, ForeignKey,
    JSON, Index, Float, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class SourceEventStatus(str, enum.Enum):
    NEW = "new"
    CORRELATED = "correlated"
    CASE_CREATED = "case_created"
    CLOSED = "closed"


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    INVESTIGATING = "investigating"
    PLANNED = "planned"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class AgentRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentType(str, enum.Enum):
    TRIAGE = "alert_triage"
    HISTORICAL = "historical_analysis"
    INSIGHT = "insight_analysis"
    REMEDIATION = "autonomous_remediation"


class EvidenceType(str, enum.Enum):
    ALERT = "alert"
    LOG = "log"
    METRIC = "metric"
    TOPOLOGY = "topology"
    COMMAND_OUTPUT = "command_output"
    CASE_NOTE = "case_note"
    EXTERNAL_CONTEXT = "external_context"


class ClaimStatus(str, enum.Enum):
    HYPOTHESIS = "hypothesis"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    ACTIONABLE = "actionable"


class MemoryType(str, enum.Enum):
    EPISODE = "episode"
    PATTERN = "pattern"
    OUTCOME = "outcome"
    FEEDBACK = "feedback"


class RemediationPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ExecutionRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled_back"


class SourceEvent(Base):
    __tablename__ = "source_event"

    id = Column(BigInteger, primary_key=True, index=True)
    legacy_event_id = Column(BigInteger, unique=True, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    source_system = Column(String(50), nullable=False, index=True)
    external_event_id = Column(String(128), index=True)
    dedup_key = Column(String(128), nullable=False, unique=True, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=True, index=True)
    netbox_device_id = Column(Integer, index=True)
    device_ip = Column(String(64), index=True)
    host = Column(String(255), index=True)
    title = Column(String(512), nullable=False)
    severity = Column(String(30), nullable=False, index=True)
    status = Column(SQLEnum(SourceEventStatus), nullable=False, default=SourceEventStatus.NEW, index=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    raw_payload = Column(JSON, default=dict)
    normalized_payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    site = relationship("Site")
    cases = relationship("CaseRecord", back_populates="source_event")

    __table_args__ = (
        Index("idx_source_event_legacy_event_id", "legacy_event_id"),
        Index("idx_source_event_source_status", "source_system", "status", "occurred_at"),
        Index("idx_source_event_site_device", "site_id", "netbox_device_id", "occurred_at"),
    )


class CaseRecord(Base):
    __tablename__ = "case_record"

    id = Column(BigInteger, primary_key=True, index=True)
    case_code = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=False)
    summary = Column(Text)
    source_event_id = Column(BigInteger, ForeignKey("source_event.id"), nullable=True, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=True, index=True)
    netbox_device_id = Column(Integer, index=True)
    device_ip = Column(String(64), index=True)
    host = Column(String(255), index=True)
    priority = Column(String(20), default="P3", index=True)
    risk_level = Column(String(20), default="medium", index=True)
    status = Column(SQLEnum(CaseStatus), nullable=False, default=CaseStatus.OPEN, index=True)
    current_phase = Column(String(50), default="intake", index=True)
    case_metadata = Column(JSON, default=dict)
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    source_event = relationship("SourceEvent", back_populates="cases")
    site = relationship("Site")
    evidences = relationship("EvidenceItem", back_populates="case", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="case", cascade="all, delete-orphan")
    claims = relationship("AgentClaim", back_populates="case", cascade="all, delete-orphan")
    memories = relationship("MemoryEntry", back_populates="case")
    remediation_plans = relationship("RemediationPlan", back_populates="case", cascade="all, delete-orphan")
    execution_runs = relationship("ExecutionRun", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_case_record_status_phase", "status", "current_phase", "opened_at"),
        Index("idx_case_record_site_device", "site_id", "netbox_device_id", "opened_at"),
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_item"

    id = Column(BigInteger, primary_key=True, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id"), nullable=False, index=True)
    source_event_id = Column(BigInteger, ForeignKey("source_event.id"), nullable=True, index=True)
    evidence_type = Column(SQLEnum(EvidenceType), nullable=False, index=True)
    source_system = Column(String(50), nullable=False, index=True)
    source_ref = Column(String(255), index=True)
    fingerprint = Column(String(128), index=True)
    device_ip = Column(String(64), index=True)
    host = Column(String(255), index=True)
    occurred_at = Column(DateTime(timezone=True), index=True)
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    freshness_seconds = Column(Float, default=0.0)
    confidence = Column(Float, default=1.0)
    raw_ref = Column(String(255))
    summary = Column(Text)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    case = relationship("CaseRecord", back_populates="evidences")
    source_event = relationship("SourceEvent")

    __table_args__ = (
        Index("idx_evidence_case_type", "case_id", "evidence_type", "created_at"),
        Index("idx_evidence_source_fingerprint", "source_system", "fingerprint"),
    )


class AgentRun(Base):
    __tablename__ = "agent_run"

    id = Column(BigInteger, primary_key=True, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id"), nullable=False, index=True)
    agent_type = Column(SQLEnum(AgentType), nullable=False, index=True)
    agent_name = Column(String(120), nullable=False, index=True)
    status = Column(SQLEnum(AgentRunStatus), nullable=False, default=AgentRunStatus.PENDING, index=True)
    input_payload = Column(JSON, default=dict)
    output_payload = Column(JSON, default=dict)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    case = relationship("CaseRecord", back_populates="agent_runs")
    claims = relationship("AgentClaim", back_populates="agent_run")

    __table_args__ = (
        Index("idx_agent_run_case_type", "case_id", "agent_type", "started_at"),
    )


class AgentClaim(Base):
    __tablename__ = "agent_claim"

    id = Column(BigInteger, primary_key=True, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id"), nullable=False, index=True)
    agent_run_id = Column(BigInteger, ForeignKey("agent_run.id"), nullable=False, index=True)
    agent_type = Column(SQLEnum(AgentType), nullable=False, index=True)
    claim_type = Column(String(100), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    status = Column(SQLEnum(ClaimStatus), nullable=False, default=ClaimStatus.HYPOTHESIS, index=True)
    confidence = Column(Float, default=0.0)
    evidence_refs = Column(JSON, default=list)
    gaps = Column(JSON, default=list)
    claim_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    case = relationship("CaseRecord", back_populates="claims")
    agent_run = relationship("AgentRun", back_populates="claims")

    __table_args__ = (
        Index("idx_agent_claim_case_type", "case_id", "agent_type", "created_at"),
    )


class MemoryEntry(Base):
    __tablename__ = "memory_entry"

    id = Column(BigInteger, primary_key=True, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id"), nullable=True, index=True)
    memory_type = Column(SQLEnum(MemoryType), nullable=False, index=True)
    memory_key = Column(String(128), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text)
    source = Column(String(50), nullable=False, default="system", index=True)
    tags = Column(JSON, default=list)
    confidence = Column(Float, default=0.0)
    success_score = Column(Float, default=0.0)
    content = Column(JSON, default=dict)
    last_accessed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    case = relationship("CaseRecord", back_populates="memories")

    __table_args__ = (
        Index("idx_memory_type_key", "memory_type", "memory_key"),
        Index("idx_memory_source_created", "source", "created_at"),
    )


class RemediationPlan(Base):
    __tablename__ = "remediation_plan"

    id = Column(BigInteger, primary_key=True, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id"), nullable=False, index=True)
    plan_code = Column(String(64), nullable=False, unique=True, index=True)
    generated_by_agent_run_id = Column(BigInteger, ForeignKey("agent_run.id"), nullable=True, index=True)
    status = Column(SQLEnum(RemediationPlanStatus), nullable=False, default=RemediationPlanStatus.DRAFT, index=True)
    execution_mode = Column(String(20), nullable=False, default="manual", index=True)
    approval_status = Column(String(20), nullable=False, default="not_required", index=True)
    risk_level = Column(String(20), nullable=False, default="medium", index=True)
    summary = Column(Text)
    plan_payload = Column(JSON, default=dict)
    rollback_payload = Column(JSON, default=dict)
    safety_checks = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    approved_at = Column(DateTime(timezone=True))

    case = relationship("CaseRecord", back_populates="remediation_plans")
    execution_runs = relationship("ExecutionRun", back_populates="remediation_plan")

    __table_args__ = (
        Index("idx_remediation_plan_case_status", "case_id", "status", "created_at"),
    )


class ExecutionRun(Base):
    __tablename__ = "execution_run"

    id = Column(BigInteger, primary_key=True, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id"), nullable=False, index=True)
    remediation_plan_id = Column(BigInteger, ForeignKey("remediation_plan.id"), nullable=False, index=True)
    executor_type = Column(String(50), nullable=False, index=True)
    executor_name = Column(String(120), nullable=False, index=True)
    status = Column(SQLEnum(ExecutionRunStatus), nullable=False, default=ExecutionRunStatus.PENDING, index=True)
    command_summary = Column(Text)
    request_payload = Column(JSON, default=dict)
    result_payload = Column(JSON, default=dict)
    audit_trail = Column(JSON, default=list)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at = Column(DateTime(timezone=True))
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    case = relationship("CaseRecord", back_populates="execution_runs")
    remediation_plan = relationship("RemediationPlan", back_populates="execution_runs")

    __table_args__ = (
        Index("idx_execution_run_plan_status", "remediation_plan_id", "status", "started_at"),
    )
