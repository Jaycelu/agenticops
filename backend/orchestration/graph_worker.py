from __future__ import annotations

import socket
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from loguru import logger

from config.settings import settings
from database import SessionLocal
from models.agent_graph import AgentGraphRun, AgentTask
from observability.metrics import metrics_registry
from orchestration.graph_engine import case_graph_engine


class AgentGraphWorker:
    def __init__(self) -> None:
        self.owner = f"{socket.gethostname()}:graph"

    async def run_once(self) -> bool:
        db = SessionLocal()
        run_id = None
        try:
            now = datetime.now(timezone.utc)
            run = db.query(AgentGraphRun).filter(
                AgentGraphRun.status.in_(["queued", "running", "waiting_evidence"]),
                AgentGraphRun.next_run_at <= now,
                or_(AgentGraphRun.lease_expires_at.is_(None), AgentGraphRun.lease_expires_at < now),
            ).order_by(AgentGraphRun.next_run_at.asc(), AgentGraphRun.created_at.asc()).with_for_update(skip_locked=True).first()
            if run is None:
                db.rollback()
                return False
            run_id = run.id
            if run.lease_expires_at is not None and run.started_at is not None:
                running = db.query(AgentTask).filter(AgentTask.graph_run_id == run.id, AgentTask.status == "running").all()
                for task in running:
                    task.status = "ready"
                    task.error_message = "recovered_after_worker_lease_expired"
                metrics_registry.increment("case_graph_resume_total")
                logger.bind(
                    request_id=(run.input_payload or {}).get("request_id"), case_id=run.case_id,
                    task_id=None, agent_run_id=None, tool_call_id=None, graph_node=run.current_node,
                    correlation_id=None, graph_run_id=run.id,
                ).warning("agent_graph_lease_recovered")
                # The task-selection query disables no autoflush explicitly, but
                # PostgreSQL's row-locking query must observe the recovered state
                # in this transaction. Flush before looking for ready work so a
                # restarted worker can resume in the same polling cycle.
                db.flush()
            run.lease_owner = self.owner
            run.lease_expires_at = now + timedelta(seconds=settings.agent_graph_lease_seconds)
            task = db.query(AgentTask).filter(
                AgentTask.graph_run_id == run.id,
                AgentTask.status == "ready",
            ).order_by(AgentTask.priority.asc(), AgentTask.created_at.asc()).with_for_update(skip_locked=True).first()
            if task is None:
                run.lease_owner = None
                run.lease_expires_at = None
                db.commit()
                return False
            db.commit()
            run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
            task = db.query(AgentTask).filter(AgentTask.id == task.id).one()
            await case_graph_engine.execute_task(db, run, task)
            run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
            run.lease_owner = None
            run.lease_expires_at = None
            db.commit()
            return True
        finally:
            db.close()


agent_graph_worker = AgentGraphWorker()
