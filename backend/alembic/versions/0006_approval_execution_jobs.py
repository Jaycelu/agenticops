"""Add frozen approvals and idempotent execution jobs.

Revision ID: 0006_approval_execution_jobs
Revises: 0005_probe_gateway
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_approval_execution_jobs"
down_revision = "0005_probe_gateway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_version",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("remediation_plan_id", sa.BigInteger(), sa.ForeignKey("remediation_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("canonical_payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("initiated_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("initiated_by_session_id", sa.String(64), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("remediation_plan_id", "version", name="uq_plan_version_number"),
    )
    op.create_index("ix_plan_version_remediation_plan_id", "plan_version", ["remediation_plan_id"])
    op.create_index("ix_plan_version_plan_hash", "plan_version", ["plan_hash"])
    op.create_index("ix_plan_version_state", "plan_version", ["state"])
    op.create_index("ix_plan_version_expires_at", "plan_version", ["expires_at"])
    op.create_index("idx_plan_version_plan_state", "plan_version", ["remediation_plan_id", "state", "expires_at"])
    op.create_table(
        "approval_decision",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("plan_version_id", sa.BigInteger(), sa.ForeignKey("plan_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("decided_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decided_by_session_id", sa.String(64), nullable=False),
        sa.Column("decided_plan_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_version_id", name="uq_approval_decision_plan_version"),
    )
    op.create_index("ix_approval_decision_plan_version_id", "approval_decision", ["plan_version_id"])
    op.create_index("ix_approval_decision_decision", "approval_decision", ["decision"])
    op.create_index("ix_approval_decision_decided_by_user_id", "approval_decision", ["decided_by_user_id"])
    op.create_table(
        "execution_job",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("plan_version_id", sa.BigInteger(), sa.ForeignKey("plan_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("remediation_plan_id", sa.BigInteger(), sa.ForeignKey("remediation_plan.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requested_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_by_session_id", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_code", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("plan_version_id", name="uq_execution_job_plan_version"),
        sa.UniqueConstraint("idempotency_key", name="uq_execution_job_idempotency_key"),
    )
    op.create_index("ix_execution_job_remediation_plan_id", "execution_job", ["remediation_plan_id"])
    op.create_index("ix_execution_job_case_id", "execution_job", ["case_id"])
    op.create_index("ix_execution_job_status", "execution_job", ["status"])
    op.create_table(
        "execution_action_result",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("execution_job_id", sa.BigInteger(), sa.ForeignKey("execution_job.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_index", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("execution_job_id", "action_index", name="uq_execution_action_index"),
    )
    op.create_index("ix_execution_action_result_execution_job_id", "execution_action_result", ["execution_job_id"])
    op.create_index("ix_execution_action_result_status", "execution_action_result", ["status"])
    op.create_table(
        "idempotency_record",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("resource_type", sa.String(80)),
        sa.Column("resource_id", sa.String(120)),
        sa.Column("response_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),
    )
    op.create_index("ix_idempotency_record_status", "idempotency_record", ["status"])
    op.create_index("ix_idempotency_record_expires_at", "idempotency_record", ["expires_at"])


def downgrade() -> None:
    op.drop_table("idempotency_record")
    op.drop_table("execution_action_result")
    op.drop_table("execution_job")
    op.drop_table("approval_decision")
    op.drop_table("plan_version")
