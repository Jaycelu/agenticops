"""Add durable ELK checkpoints, aggregation, and noise-reduction snapshots.

Revision ID: 0009_elk_ingestion
Revises: 0008_verification_loop
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_elk_ingestion"
down_revision = "0008_verification_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_checkpoint",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope_id", sa.Integer(), sa.ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("cursor_timestamp", sa.DateTime(timezone=True)),
        sa.Column("cursor_document_id", sa.String(512)),
        sa.Column("lease_owner", sa.String(120)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_documents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lag_seconds", sa.Integer()),
        sa.Column("last_error_code", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ingestion_checkpoint_lease_expires_at", "ingestion_checkpoint", ["lease_expires_at"])
    op.create_table(
        "ingested_log_event",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope_id", sa.Integer(), sa.ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_document_id", sa.String(512), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_key", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("normalized_message", sa.Text(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("decision", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("aggregation_bucket_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scope_id", "external_document_id", name="uq_ingested_log_scope_document"),
    )
    for name, columns in (
        ("ix_ingested_log_event_scope_id", ["scope_id"]),
        ("ix_ingested_log_event_occurred_at", ["occurred_at"]),
        ("ix_ingested_log_event_device_key", ["device_key"]),
        ("ix_ingested_log_event_severity", ["severity"]),
        ("ix_ingested_log_event_signature", ["signature"]),
        ("ix_ingested_log_event_aggregation_bucket_id", ["aggregation_bucket_id"]),
        ("ix_ingested_log_event_decision", ["decision"]),
        ("idx_ingested_log_scope_cursor", ["scope_id", "occurred_at", "external_document_id"]),
        ("idx_ingested_log_signature_time", ["signature", "occurred_at"]),
    ):
        op.create_index(name, "ingested_log_event", columns)
    op.create_table(
        "log_aggregation_bucket",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope_id", sa.Integer(), sa.ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_key", sa.String(255), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_document_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decision_reason", sa.String(255), nullable=False),
        sa.Column("emitted_case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="SET NULL")),
        sa.Column("emitted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scope_id", "window_start", "device_key", "signature", name="uq_log_aggregation_bucket"),
    )
    for name, columns in (
        ("ix_log_aggregation_bucket_scope_id", ["scope_id"]),
        ("ix_log_aggregation_bucket_window_start", ["window_start"]),
        ("ix_log_aggregation_bucket_device_key", ["device_key"]),
        ("ix_log_aggregation_bucket_signature", ["signature"]),
        ("ix_log_aggregation_bucket_severity", ["severity"]),
        ("ix_log_aggregation_bucket_decision", ["decision"]),
        ("ix_log_aggregation_bucket_emitted_case_id", ["emitted_case_id"]),
        ("idx_log_bucket_decision_time", ["decision", "window_start"]),
    ):
        op.create_index(name, "log_aggregation_bucket", columns)
    op.create_foreign_key(
        "fk_ingested_log_event_aggregation_bucket",
        "ingested_log_event",
        "log_aggregation_bucket",
        ["aggregation_bucket_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "noise_reduction_snapshot",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope_id", sa.Integer(), sa.ForeignKey("log_scope.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False),
        sa.Column("bucket_count", sa.Integer(), nullable=False),
        sa.Column("emitted_count", sa.Integer(), nullable=False),
        sa.Column("suppressed_count", sa.Integer(), nullable=False),
        sa.Column("critical_suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_noise_reduction_snapshot_scope_id", "noise_reduction_snapshot", ["scope_id"])
    op.create_index("ix_noise_reduction_snapshot_rule_version", "noise_reduction_snapshot", ["rule_version"])


def downgrade() -> None:
    op.drop_table("noise_reduction_snapshot")
    op.drop_table("ingested_log_event")
    op.drop_table("log_aggregation_bucket")
    op.drop_table("ingestion_checkpoint")
