"""Add worker heartbeat for deployment health and observability.

Revision ID: 0010_worker_runtime
Revises: 0009_elk_ingestion
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_worker_runtime"
down_revision = "0009_elk_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeat",
        sa.Column("worker_name", sa.String(120), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_worker_heartbeat_last_seen_at", "worker_heartbeat", ["last_seen_at"])


def downgrade() -> None:
    op.drop_table("worker_heartbeat")
