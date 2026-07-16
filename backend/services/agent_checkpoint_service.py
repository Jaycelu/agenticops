from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from models.agent_graph import AgentBudget, AgentCheckpoint, AgentTask


class AgentCheckpointService:
    def create(self, db: Session, graph_run, state_payload: dict) -> AgentCheckpoint:
        budget = db.query(AgentBudget).filter(AgentBudget.graph_run_id == graph_run.id).one()
        pending = db.query(AgentTask).filter(
            AgentTask.graph_run_id == graph_run.id,
            AgentTask.status.in_(["pending", "ready", "running", "waiting_evidence", "waiting_agent", "waiting_human"]),
        ).order_by(AgentTask.id.asc()).all()
        checkpoint = AgentCheckpoint(
            graph_run_id=graph_run.id,
            case_id=graph_run.case_id,
            graph_version=graph_run.graph_version,
            current_node=graph_run.current_node,
            state_payload=state_payload,
            pending_tasks=[{"id": item.id, "node": item.graph_node, "status": item.status} for item in pending],
            budget_snapshot={
                "agent_runs": [budget.used_agent_runs, budget.max_agent_runs],
                "llm_calls": [budget.used_llm_calls, budget.max_llm_calls],
                "tool_calls": [budget.used_tool_calls, budget.max_tool_calls],
                "probe_calls": [budget.used_probe_calls, budget.max_probe_calls],
                "replan_count": [budget.used_replan_count, budget.max_replan_count],
                "runtime_seconds": [budget.used_runtime_seconds, budget.max_runtime_seconds],
                "target_devices": [len(budget.target_device_ids or []), budget.max_target_devices],
            },
            resume_token=secrets.token_urlsafe(32),
        )
        db.add(checkpoint)
        db.flush()
        return checkpoint

    def latest(self, db: Session, graph_run_id: str) -> AgentCheckpoint | None:
        return db.query(AgentCheckpoint).filter(AgentCheckpoint.graph_run_id == graph_run_id).order_by(AgentCheckpoint.id.desc()).first()


agent_checkpoint_service = AgentCheckpointService()
