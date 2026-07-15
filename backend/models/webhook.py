from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoint"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    event_types = Column(JSON, nullable=False, default=list)
    secret_encrypted = Column(Text, nullable=False)
    secret_fingerprint = Column(String(16), nullable=False)
    timeout_seconds = Column(Integer, nullable=False, default=10)
    max_attempts = Column(Integer, nullable=False, default=8)
    created_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OutboxEvent(Base):
    __tablename__ = "outbox_event"

    id = Column(BigInteger, primary_key=True)
    event_id = Column(String(36), nullable=False, unique=True, index=True)
    event_type = Column(String(120), nullable=False, index=True)
    payload_version = Column(Integer, nullable=False, default=1)
    aggregate_type = Column(String(80), nullable=False, index=True)
    aggregate_id = Column(String(160), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    __table_args__ = (Index("idx_outbox_aggregate", "aggregate_type", "aggregate_id", "created_at"),)


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"

    id = Column(BigInteger, primary_key=True)
    outbox_event_id = Column(BigInteger, ForeignKey("outbox_event.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint_id = Column(BigInteger, ForeignKey("webhook_endpoint.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    lease_expires_at = Column(DateTime(timezone=True), index=True)
    last_http_status = Column(Integer)
    last_error_code = Column(String(120))
    response_digest = Column(String(64))
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("outbox_event_id", "endpoint_id", name="uq_webhook_delivery_event_endpoint"),
        Index("idx_webhook_delivery_claim", "status", "next_attempt_at", "lease_expires_at"),
    )
