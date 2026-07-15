"""Add generic webhook endpoints and transactional outbox.

Revision ID: 0007_webhook_outbox
Revises: 0006_approval_execution_jobs
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_webhook_outbox"
down_revision = "0006_approval_execution_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoint",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("event_types", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("secret_fingerprint", sa.String(16), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_endpoint_enabled", "webhook_endpoint", ["enabled"])
    op.create_table(
        "outbox_event",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        sa.Column("aggregate_id", sa.String(160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_outbox_event_event_id", "outbox_event", ["event_id"])
    op.create_index("ix_outbox_event_event_type", "outbox_event", ["event_type"])
    op.create_index("ix_outbox_event_aggregate_type", "outbox_event", ["aggregate_type"])
    op.create_index("ix_outbox_event_aggregate_id", "outbox_event", ["aggregate_id"])
    op.create_index("ix_outbox_event_created_at", "outbox_event", ["created_at"])
    op.create_index("idx_outbox_aggregate", "outbox_event", ["aggregate_type", "aggregate_id", "created_at"])
    op.create_table(
        "webhook_delivery",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("outbox_event_id", sa.BigInteger(), sa.ForeignKey("outbox_event.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_id", sa.BigInteger(), sa.ForeignKey("webhook_endpoint.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_http_status", sa.Integer()),
        sa.Column("last_error_code", sa.String(120)),
        sa.Column("response_digest", sa.String(64)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("outbox_event_id", "endpoint_id", name="uq_webhook_delivery_event_endpoint"),
    )
    op.create_index("ix_webhook_delivery_outbox_event_id", "webhook_delivery", ["outbox_event_id"])
    op.create_index("ix_webhook_delivery_endpoint_id", "webhook_delivery", ["endpoint_id"])
    op.create_index("ix_webhook_delivery_status", "webhook_delivery", ["status"])
    op.create_index("ix_webhook_delivery_next_attempt_at", "webhook_delivery", ["next_attempt_at"])
    op.create_index("ix_webhook_delivery_lease_expires_at", "webhook_delivery", ["lease_expires_at"])
    op.create_index("idx_webhook_delivery_claim", "webhook_delivery", ["status", "next_attempt_at", "lease_expires_at"])


def downgrade() -> None:
    op.drop_table("webhook_delivery")
    op.drop_table("outbox_event")
    op.drop_table("webhook_endpoint")
