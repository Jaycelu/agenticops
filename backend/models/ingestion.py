from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class IngestionCheckpoint(Base):
    __tablename__ = "ingestion_checkpoint"

    id = Column(BigInteger, primary_key=True)
    scope_id = Column(Integer, ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False, unique=True)
    cursor_timestamp = Column(DateTime(timezone=True))
    cursor_document_id = Column(String(512))
    lease_owner = Column(String(120))
    lease_expires_at = Column(DateTime(timezone=True), index=True)
    last_success_at = Column(DateTime(timezone=True))
    last_page_count = Column(Integer, nullable=False, default=0)
    total_documents = Column(BigInteger, nullable=False, default=0)
    lag_seconds = Column(Integer)
    last_error_code = Column(String(120))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class IngestedLogEvent(Base):
    __tablename__ = "ingested_log_event"

    id = Column(BigInteger, primary_key=True)
    scope_id = Column(Integer, ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False, index=True)
    external_document_id = Column(String(512), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    device_key = Column(String(255), nullable=False, index=True)
    severity = Column(String(30), nullable=False, index=True)
    signature = Column(String(64), nullable=False, index=True)
    normalized_message = Column(Text, nullable=False)
    source_metadata = Column(JSON, nullable=False, default=dict)
    decision = Column(String(30), nullable=False, default="pending", index=True)
    aggregation_bucket_id = Column(BigInteger, ForeignKey("log_aggregation_bucket.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("scope_id", "external_document_id", name="uq_ingested_log_scope_document"),
        Index("idx_ingested_log_scope_cursor", "scope_id", "occurred_at", "external_document_id"),
        Index("idx_ingested_log_signature_time", "signature", "occurred_at"),
    )


class LogAggregationBucket(Base):
    __tablename__ = "log_aggregation_bucket"

    id = Column(BigInteger, primary_key=True)
    scope_id = Column(Integer, ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False)
    device_key = Column(String(255), nullable=False, index=True)
    signature = Column(String(64), nullable=False, index=True)
    severity = Column(String(30), nullable=False, index=True)
    event_count = Column(Integer, nullable=False, default=0)
    sample_document_ids = Column(JSON, nullable=False, default=list)
    rule_version = Column(String(40), nullable=False)
    decision = Column(String(30), nullable=False, index=True)
    decision_reason = Column(String(255), nullable=False)
    emitted_case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="SET NULL"), index=True)
    emitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("scope_id", "window_start", "device_key", "signature", name="uq_log_aggregation_bucket"),
        Index("idx_log_bucket_decision_time", "decision", "window_start"),
    )


class NoiseReductionSnapshot(Base):
    __tablename__ = "noise_reduction_snapshot"

    id = Column(BigInteger, primary_key=True)
    scope_id = Column(Integer, ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_version = Column(String(40), nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    input_count = Column(Integer, nullable=False)
    bucket_count = Column(Integer, nullable=False)
    emitted_count = Column(Integer, nullable=False)
    suppressed_count = Column(Integer, nullable=False)
    critical_suppressed_count = Column(Integer, nullable=False, default=0)
    metrics = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
