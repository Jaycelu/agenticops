"""Add the durable multi-agent diagnostic graph.

Revision ID: 0011_multi_agent_graph
Revises: 0010_worker_runtime
Create Date: 2026-07-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_multi_agent_graph"
down_revision = "0010_worker_runtime"
branch_labels = None
depends_on = None


JSON_OBJECT = sa.text("'{}'::json")
JSON_ARRAY = sa.text("'[]'::json")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in (
            "NEW", "NORMALIZED", "EVIDENCE_COLLECTING", "DIAGNOSING", "HYPOTHESIS_REVIEW",
            "PLANNING", "SAFETY_REVIEW", "AWAITING_APPROVAL", "OBSERVING", "ROLLED_BACK", "FAILED",
        ):
            op.execute(f"ALTER TYPE casestatus ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table(
        "agent_graph_run",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("graph_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("current_state", sa.String(40), nullable=False),
        sa.Column("current_node", sa.String(120), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("result_payload", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("stop_reason", sa.String(255)),
        sa.Column("error_message", sa.Text()),
        sa.Column("forced_from_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="SET NULL")),
        sa.Column("requested_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="SET NULL")),
        sa.Column("requested_by_session_id", sa.String(64)),
        sa.Column("lease_owner", sa.String(120)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for name, cols in (
        ("ix_agent_graph_run_case_id", ["case_id"]), ("ix_agent_graph_run_status", ["status"]),
        ("ix_agent_graph_run_lease_expires_at", ["lease_expires_at"]), ("ix_agent_graph_run_next_run_at", ["next_run_at"]),
        ("idx_agent_graph_run_claim", ["status", "next_run_at", "lease_expires_at"]),
    ):
        op.create_index(name, "agent_graph_run", cols)
    op.create_index(
        "uq_agent_graph_run_case_active", "agent_graph_run", ["case_id"], unique=True,
        postgresql_where=sa.text("status IN ('queued','running','waiting_evidence','waiting_human','paused')"),
    )

    op.create_table(
        "agent_task",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_task_id", sa.BigInteger(), sa.ForeignKey("agent_task.id", ondelete="SET NULL")),
        sa.Column("task_code", sa.String(120), nullable=False), sa.Column("task_type", sa.String(60), nullable=False),
        sa.Column("graph_node", sa.String(120), nullable=False), sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("assigned_agent_type", sa.String(80)), sa.Column("assigned_agent_name", sa.String(120)),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("input_payload", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("output_payload", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("error_message", sa.Text()), sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("insight_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(200), nullable=False), sa.Column("deadline_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(120), nullable=False, server_default="supervisor"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("graph_run_id", "idempotency_key", name="uq_agent_task_graph_idempotency"),
    )
    for name, cols in (
        ("ix_agent_task_graph_run_id", ["graph_run_id"]), ("ix_agent_task_case_id", ["case_id"]),
        ("ix_agent_task_parent_task_id", ["parent_task_id"]), ("ix_agent_task_task_type", ["task_type"]),
        ("ix_agent_task_graph_node", ["graph_node"]), ("ix_agent_task_status", ["status"]),
        ("idx_agent_task_ready", ["graph_run_id", "status", "priority", "created_at"]),
    ):
        op.create_index(name, "agent_task", cols)

    op.create_table(
        "agent_budget",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in (
            "max_agent_runs", "max_llm_calls", "max_tool_calls", "max_probe_calls", "max_replan_count", "max_runtime_seconds", "max_target_devices"
        )],
        *[sa.Column(name, sa.Integer(), nullable=False, server_default="0") for name in (
            "used_agent_runs", "used_llm_calls", "used_tool_calls", "used_probe_calls", "used_replan_count"
        )],
        sa.Column("used_runtime_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("target_device_ids", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("exhausted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("exhausted_reason", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_budget_case_id", "agent_budget", ["case_id"])
    op.create_index("ix_agent_budget_exhausted", "agent_budget", ["exhausted"])

    op.add_column("agent_run", sa.Column("graph_run_id", sa.String(64)))
    op.add_column("agent_run", sa.Column("task_id", sa.BigInteger()))
    op.create_foreign_key("fk_agent_run_graph_run", "agent_run", "agent_graph_run", ["graph_run_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_agent_run_task", "agent_run", "agent_task", ["task_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_agent_run_graph_run_id", "agent_run", ["graph_run_id"])
    op.create_index("ix_agent_run_task_id", "agent_run", ["task_id"])

    op.create_table(
        "agent_message",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("agent_task.id", ondelete="SET NULL")),
        sa.Column("sender_type", sa.String(40), nullable=False), sa.Column("sender_id", sa.String(120)),
        sa.Column("receiver_type", sa.String(40), nullable=False), sa.Column("receiver_id", sa.String(120)),
        sa.Column("message_type", sa.String(50), nullable=False), sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("artifact_refs", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    _indexes("agent_message", ("graph_run_id", "case_id", "task_id", "message_type", "correlation_id", "created_at"))

    op.create_table(
        "agent_tool_call",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("agent_task.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_run_id", sa.BigInteger(), sa.ForeignKey("agent_run.id", ondelete="SET NULL")),
        sa.Column("tool_id", sa.String(120), nullable=False), sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False), sa.Column("policy_decision", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("result_payload", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("error_message", sa.Text()), sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("graph_run_id", "idempotency_key", name="uq_agent_tool_call_graph_idempotency"),
    )
    _indexes("agent_tool_call", ("graph_run_id", "case_id", "task_id", "agent_run_id", "tool_id", "status"))

    op.add_column("evidence_item", sa.Column("task_id", sa.BigInteger()))
    op.add_column("evidence_item", sa.Column("tool_call_id", sa.BigInteger()))
    op.add_column("evidence_item", sa.Column("probe_run_id", sa.BigInteger()))
    op.create_foreign_key("fk_evidence_item_task", "evidence_item", "agent_task", ["task_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_evidence_item_tool_call", "evidence_item", "agent_tool_call", ["tool_call_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_evidence_item_probe_run", "evidence_item", "probe_run", ["probe_run_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_evidence_item_task_id", "evidence_item", ["task_id"])
    op.create_index("ix_evidence_item_tool_call_id", "evidence_item", ["tool_call_id"])
    op.create_index("ix_evidence_item_probe_run_id", "evidence_item", ["probe_run_id"])

    op.create_table(
        "agent_checkpoint",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("graph_version", sa.String(40), nullable=False), sa.Column("current_node", sa.String(120), nullable=False),
        sa.Column("state_payload", sa.JSON(), nullable=False), sa.Column("pending_tasks", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("budget_snapshot", sa.JSON(), nullable=False), sa.Column("resume_token", sa.String(120), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    _indexes("agent_checkpoint", ("graph_run_id", "case_id", "created_at"))

    op.create_table(
        "case_timeline_event",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="SET NULL")),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("agent_task.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(60), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=JSON_OBJECT), sa.Column("actor_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(120)), sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    _indexes("case_timeline_event", ("case_id", "graph_run_id", "task_id", "event_type", "correlation_id", "created_at"))

    op.create_table(
        "case_state_transition",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="SET NULL")),
        sa.Column("from_state", sa.String(40), nullable=False), sa.Column("to_state", sa.String(40), nullable=False),
        sa.Column("trigger_type", sa.String(40), nullable=False), sa.Column("trigger_id", sa.String(120)),
        sa.Column("reason", sa.Text(), nullable=False), sa.Column("agent_run_id", sa.BigInteger(), sa.ForeignKey("agent_run.id", ondelete="SET NULL")),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("agent_task.id", ondelete="SET NULL")),
        sa.Column("evidence_ids", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("correlation_id", sa.String(80), nullable=False), sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    _indexes("case_state_transition", ("case_id", "graph_run_id", "to_state", "correlation_id", "created_at"))

    op.create_table(
        "case_hypothesis",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("graph_run_id", sa.String(64), sa.ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.BigInteger(), sa.ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("agent_task.id", ondelete="SET NULL")),
        sa.Column("hypothesis_code", sa.String(120), nullable=False), sa.Column("cause_code", sa.String(120), nullable=False),
        sa.Column("cause", sa.Text(), nullable=False), sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("contradicting_evidence_ids", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("missing_evidence", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("next_probe_requests", sa.JSON(), nullable=False, server_default=JSON_ARRAY),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("insight_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critic_decision", sa.String(30)), sa.Column("critic_payload", sa.JSON(), nullable=False, server_default=JSON_OBJECT),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("graph_run_id", "hypothesis_code", "insight_round", name="uq_case_hypothesis_round"),
    )
    _indexes("case_hypothesis", ("graph_run_id", "case_id", "task_id", "status"))


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for name in ("probe_run_id", "tool_call_id", "task_id"):
        op.drop_index(f"ix_evidence_item_{name}", table_name="evidence_item")
    for name in ("fk_evidence_item_probe_run", "fk_evidence_item_tool_call", "fk_evidence_item_task"):
        op.drop_constraint(name, "evidence_item", type_="foreignkey")
    for name in ("probe_run_id", "tool_call_id", "task_id"):
        op.drop_column("evidence_item", name)
    for table in (
        "case_hypothesis", "case_state_transition", "case_timeline_event", "agent_checkpoint",
        "agent_tool_call", "agent_message",
    ):
        op.drop_table(table)
    op.drop_index("ix_agent_run_task_id", table_name="agent_run")
    op.drop_index("ix_agent_run_graph_run_id", table_name="agent_run")
    op.drop_constraint("fk_agent_run_task", "agent_run", type_="foreignkey")
    op.drop_constraint("fk_agent_run_graph_run", "agent_run", type_="foreignkey")
    op.drop_column("agent_run", "task_id")
    op.drop_column("agent_run", "graph_run_id")
    op.drop_table("agent_budget")
    op.drop_table("agent_task")
    op.drop_table("agent_graph_run")
    # PostgreSQL enum values are intentionally retained; removing values is destructive.
