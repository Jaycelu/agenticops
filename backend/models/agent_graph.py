from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.sql import func

from database import Base


class AgentGraphRun(Base):
    __tablename__ = "agent_graph_run"

    id = Column(String(64), primary_key=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    graph_version = Column(String(40), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    current_state = Column(String(40), nullable=False)
    current_node = Column(String(120), nullable=False)
    input_payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    result_payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    stop_reason = Column(String(255))
    error_message = Column(Text)
    forced_from_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="SET NULL"))
    requested_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"))
    requested_by_session_id = Column(String(64))
    lease_owner = Column(String(120))
    lease_expires_at = Column(DateTime(timezone=True), index=True)
    next_run_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_agent_graph_run_claim", "status", "next_run_at", "lease_expires_at"),
        Index(
            "uq_agent_graph_run_case_active",
            "case_id",
            unique=True,
            postgresql_where=status.in_(["queued", "running", "waiting_evidence", "waiting_human", "paused"]),
        ),
    )


class AgentTask(Base):
    __tablename__ = "agent_task"

    id = Column(BigInteger, primary_key=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_task_id = Column(BigInteger, ForeignKey("agent_task.id", ondelete="SET NULL"), index=True)
    task_code = Column(String(120), nullable=False)
    task_type = Column(String(60), nullable=False, index=True)
    graph_node = Column(String(120), nullable=False, index=True)
    goal = Column(Text, nullable=False)
    assigned_agent_type = Column(String(80))
    assigned_agent_name = Column(String(120))
    status = Column(String(30), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=100, server_default="100")
    input_payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    output_payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    error_message = Column(Text)
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    insight_round = Column(Integer, nullable=False, default=0, server_default="0")
    idempotency_key = Column(String(200), nullable=False)
    deadline_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    created_by = Column(String(120), nullable=False, default="supervisor", server_default="supervisor")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("graph_run_id", "idempotency_key", name="uq_agent_task_graph_idempotency"),
        Index("idx_agent_task_ready", "graph_run_id", "status", "priority", "created_at"),
    )


class AgentMessage(Base):
    __tablename__ = "agent_message"

    id = Column(BigInteger, primary_key=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(BigInteger, ForeignKey("agent_task.id", ondelete="SET NULL"), index=True)
    sender_type = Column(String(40), nullable=False)
    sender_id = Column(String(120))
    receiver_type = Column(String(40), nullable=False)
    receiver_id = Column(String(120))
    message_type = Column(String(50), nullable=False, index=True)
    content = Column(JSON, nullable=False)
    artifact_refs = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    correlation_id = Column(String(80), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class AgentToolCall(Base):
    __tablename__ = "agent_tool_call"

    id = Column(BigInteger, primary_key=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(BigInteger, ForeignKey("agent_task.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_id = Column(BigInteger, ForeignKey("agent_run.id", ondelete="SET NULL"), index=True)
    tool_id = Column(String(120), nullable=False, index=True)
    mode = Column(String(30), nullable=False)
    request_payload = Column(JSON, nullable=False)
    policy_decision = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    status = Column(String(30), nullable=False, index=True)
    result_payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    error_message = Column(Text)
    idempotency_key = Column(String(200), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("graph_run_id", "idempotency_key", name="uq_agent_tool_call_graph_idempotency"),)


class AgentBudget(Base):
    __tablename__ = "agent_budget"

    id = Column(BigInteger, primary_key=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False, unique=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    max_agent_runs = Column(Integer, nullable=False)
    max_llm_calls = Column(Integer, nullable=False)
    max_tool_calls = Column(Integer, nullable=False)
    max_probe_calls = Column(Integer, nullable=False)
    max_replan_count = Column(Integer, nullable=False)
    max_runtime_seconds = Column(Integer, nullable=False)
    max_target_devices = Column(Integer, nullable=False)
    used_agent_runs = Column(Integer, nullable=False, default=0, server_default="0")
    used_llm_calls = Column(Integer, nullable=False, default=0, server_default="0")
    used_tool_calls = Column(Integer, nullable=False, default=0, server_default="0")
    used_probe_calls = Column(Integer, nullable=False, default=0, server_default="0")
    used_replan_count = Column(Integer, nullable=False, default=0, server_default="0")
    used_runtime_seconds = Column(Float, nullable=False, default=0.0, server_default="0")
    target_device_ids = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    exhausted = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    exhausted_reason = Column(String(120))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoint"

    id = Column(BigInteger, primary_key=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    graph_version = Column(String(40), nullable=False)
    current_node = Column(String(120), nullable=False)
    state_payload = Column(JSON, nullable=False)
    pending_tasks = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    budget_snapshot = Column(JSON, nullable=False)
    resume_token = Column(String(120), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class CaseTimelineEvent(Base):
    __tablename__ = "case_timeline_event"

    id = Column(BigInteger, primary_key=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="SET NULL"), index=True)
    task_id = Column(BigInteger, ForeignKey("agent_task.id", ondelete="SET NULL"), index=True)
    event_type = Column(String(60), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    actor_type = Column(String(40), nullable=False)
    actor_id = Column(String(120))
    correlation_id = Column(String(80), nullable=False, index=True)
    idempotency_key = Column(String(200), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class CaseStateTransition(Base):
    __tablename__ = "case_state_transition"

    id = Column(BigInteger, primary_key=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="SET NULL"), index=True)
    from_state = Column(String(40), nullable=False)
    to_state = Column(String(40), nullable=False, index=True)
    trigger_type = Column(String(40), nullable=False)
    trigger_id = Column(String(120))
    reason = Column(Text, nullable=False)
    agent_run_id = Column(BigInteger, ForeignKey("agent_run.id", ondelete="SET NULL"))
    task_id = Column(BigInteger, ForeignKey("agent_task.id", ondelete="SET NULL"))
    evidence_ids = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    correlation_id = Column(String(80), nullable=False, index=True)
    idempotency_key = Column(String(200), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class CaseHypothesis(Base):
    __tablename__ = "case_hypothesis"

    id = Column(BigInteger, primary_key=True)
    graph_run_id = Column(String(64), ForeignKey("agent_graph_run.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(BigInteger, ForeignKey("case_record.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(BigInteger, ForeignKey("agent_task.id", ondelete="SET NULL"), index=True)
    hypothesis_code = Column(String(120), nullable=False)
    cause_code = Column(String(120), nullable=False)
    cause = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    supporting_evidence_ids = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    contradicting_evidence_ids = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    missing_evidence = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    next_probe_requests = Column(JSON, nullable=False, default=list, server_default=text("'[]'::json"))
    status = Column(String(30), nullable=False, index=True)
    insight_round = Column(Integer, nullable=False, default=0, server_default="0")
    critic_decision = Column(String(30))
    critic_payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("graph_run_id", "hypothesis_code", "insight_round", name="uq_case_hypothesis_round"),)
