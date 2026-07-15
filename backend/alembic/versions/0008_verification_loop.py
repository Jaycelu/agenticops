"""Add persisted pre-change baselines and verification rounds.

Revision ID: 0008_verification_loop
Revises: 0007_webhook_outbox
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_verification_loop"
down_revision = "0007_webhook_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_run",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("execution_job_id", sa.BigInteger(), sa.ForeignKey("execution_job.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_run_id", sa.BigInteger(), sa.ForeignKey("execution_run.id", ondelete="SET NULL")),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_index", sa.Integer(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("rounds_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_check_at", sa.DateTime(timezone=True)),
        sa.Column("verdict_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("execution_job_id", "action_index", name="uq_verification_run_job_action"),
    )
    op.create_index("ix_verification_run_execution_job_id", "verification_run", ["execution_job_id"])
    op.create_index("ix_verification_run_execution_run_id", "verification_run", ["execution_run_id"])
    op.create_index("ix_verification_run_case_id", "verification_run", ["case_id"])
    op.create_index("ix_verification_run_status", "verification_run", ["status"])
    op.create_index("ix_verification_run_next_check_at", "verification_run", ["next_check_at"])
    op.create_index("idx_verification_run_due", "verification_run", ["status", "next_check_at"])
    op.create_table(
        "baseline_snapshot",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("verification_run_id", sa.BigInteger(), sa.ForeignKey("verification_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_id", sa.String(120), nullable=False),
        sa.Column("target_key", sa.String(512), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source_collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("verification_run_id", "check_id", name="uq_baseline_run_check"),
    )
    op.create_index("ix_baseline_snapshot_verification_run_id", "baseline_snapshot", ["verification_run_id"])
    op.create_table(
        "verification_check",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("verification_run_id", sa.BigInteger(), sa.ForeignKey("verification_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_snapshot_id", sa.BigInteger(), sa.ForeignKey("baseline_snapshot.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("check_id", sa.String(120), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("observed", sa.JSON(), nullable=False),
        sa.Column("freshness_seconds", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("verification_run_id", "check_id", "round_number", name="uq_verification_check_round"),
    )
    op.create_index("ix_verification_check_verification_run_id", "verification_check", ["verification_run_id"])
    op.create_index("ix_verification_check_verdict", "verification_check", ["verdict"])


def downgrade() -> None:
    op.drop_table("verification_check")
    op.drop_table("baseline_snapshot")
    op.drop_table("verification_run")
