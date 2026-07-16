from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from models.agent_graph import AgentMessage, AgentTask
from observability.metrics import metrics_registry
from services.case_timeline_service import case_timeline_service


TASK_TRANSITIONS = {
    "pending": {"ready", "cancelled"},
    "ready": {"running", "cancelled", "timed_out"},
    "running": {"waiting_evidence", "waiting_agent", "waiting_human", "completed", "failed", "timed_out"},
    "waiting_evidence": {"ready", "cancelled", "timed_out"},
    "waiting_agent": {"ready", "cancelled", "timed_out"},
    "waiting_human": {"ready", "cancelled", "timed_out"},
    "failed": {"ready", "cancelled"},
}


class AgentTaskService:
    def create(
        self,
        db: Session,
        *,
        graph_run_id: str,
        case_id: int,
        task_type: str,
        graph_node: str,
        goal: str,
        idempotency_key: str,
        assigned_agent_type: str | None = None,
        assigned_agent_name: str | None = None,
        input_payload: dict[str, Any] | None = None,
        priority: int = 100,
        parent_task_id: int | None = None,
        insight_round: int = 0,
        max_attempts: int = 3,
        deadline_at=None,
        created_by: str = "supervisor",
        correlation_id: str | None = None,
    ) -> AgentTask:
        existing = db.query(AgentTask).filter(
            AgentTask.graph_run_id == graph_run_id,
            AgentTask.idempotency_key == idempotency_key,
        ).first()
        if existing is not None:
            return existing
        task = AgentTask(
            graph_run_id=graph_run_id,
            case_id=case_id,
            parent_task_id=parent_task_id,
            task_code=f"{graph_node}:{insight_round}:{idempotency_key[-12:]}",
            task_type=task_type,
            graph_node=graph_node,
            goal=goal,
            assigned_agent_type=assigned_agent_type,
            assigned_agent_name=assigned_agent_name,
            status="ready",
            priority=priority,
            input_payload=input_payload or {},
            idempotency_key=idempotency_key,
            insight_round=insight_round,
            max_attempts=max_attempts,
            deadline_at=deadline_at,
            created_by=created_by,
        )
        db.add(task)
        db.flush()
        cid = correlation_id or str(uuid.uuid4())
        message = AgentMessage(
            graph_run_id=graph_run_id,
            case_id=case_id,
            task_id=task.id,
            sender_type="supervisor",
            sender_id=created_by,
            receiver_type="agent" if assigned_agent_type else "graph_node",
            receiver_id=assigned_agent_type or graph_node,
            message_type="task_assignment",
            content={"goal": goal, "input": input_payload or {}},
            artifact_refs=[],
            correlation_id=cid,
        )
        db.add(message)
        case_timeline_service.append(
            db,
            case_id=case_id,
            graph_run_id=graph_run_id,
            task_id=task.id,
            event_type="agent_task",
            title=f"Task ready: {graph_node}",
            actor_type="supervisor",
            actor_id=created_by,
            correlation_id=cid,
            idempotency_key=f"task-created:{graph_run_id}:{idempotency_key}",
            payload={"task_type": task_type, "goal": goal, "status": "ready"},
        )
        metrics_registry.increment("agent_task_total", task_type=task_type, status="ready")
        metrics_registry.increment("agent_message_total", message_type="task_assignment")
        return task

    def transition(self, db: Session, task: AgentTask, to_status: str, *, output=None, error=None) -> AgentTask:
        current = task.status
        if current == to_status:
            return task
        if to_status not in TASK_TRANSITIONS.get(current, set()):
            raise ValueError(f"illegal task transition: {current} -> {to_status}")
        now = datetime.now(timezone.utc)
        task.status = to_status
        if to_status == "running":
            task.started_at = task.started_at or now
            task.attempt_count += 1
        if to_status in {"completed", "failed", "cancelled", "timed_out"}:
            task.finished_at = now
        if output is not None:
            task.output_payload = output
        if error is not None:
            task.error_message = str(error)[:4000]
        db.flush()
        metrics_registry.increment("agent_task_total", task_type=task.task_type, status=to_status)
        return task


agent_task_service = AgentTaskService()
