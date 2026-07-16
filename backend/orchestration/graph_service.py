from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit.service import security_audit_service
from auth.schemas import Principal
from config.settings import settings
from models.agent_graph import AgentBudget, AgentGraphRun, AgentTask
from models.agenticops import CaseRecord
from services.agent_task_service import agent_task_service
from services.case_timeline_service import case_timeline_service


ACTIVE_GRAPH_STATUSES = {"queued", "running", "waiting_evidence", "waiting_human", "paused"}
TERMINAL_CASE_STATES = {"resolved", "rolled_back", "closed"}
GRAPH_VERSION = "diagnostic_v1"


class GraphConflict(RuntimeError):
    pass


class GraphService:
    def enqueue(
        self,
        db: Session,
        *,
        case_id: int,
        input_payload: dict[str, Any],
        principal: Principal | None = None,
        force_restart: bool = False,
    ) -> tuple[AgentGraphRun, bool]:
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).with_for_update().first()
        if case is None:
            raise LookupError("case not found")
        active = db.query(AgentGraphRun).filter(
            AgentGraphRun.case_id == case_id,
            AgentGraphRun.status.in_(ACTIVE_GRAPH_STATUSES),
        ).order_by(AgentGraphRun.created_at.desc()).first()
        if active and not force_restart:
            return active, True
        forced_from = None
        if active:
            forced_from = active.id
            active.status = "cancelled"
            active.stop_reason = "force_restart"
            active.finished_at = datetime.now(timezone.utc)
            db.query(AgentTask).filter(
                AgentTask.graph_run_id == active.id,
                AgentTask.status.in_(["pending", "ready", "running", "waiting_evidence", "waiting_agent", "waiting_human"]),
            ).update({"status": "cancelled", "finished_at": datetime.now(timezone.utc)}, synchronize_session=False)
            case_timeline_service.append(
                db, case_id=case_id, graph_run_id=active.id, event_type="graph_run", title="Graph run cancelled by force restart",
                actor_type="human", actor_id=str(principal.user_id) if principal else "system",
                idempotency_key=f"graph-force-cancel:{active.id}", payload={"reason": "force_restart"},
            )
        graph_run_id = f"gr_{uuid.uuid4().hex}"
        run = AgentGraphRun(
            id=graph_run_id,
            case_id=case_id,
            graph_version=GRAPH_VERSION,
            status="queued",
            current_state=(case.status.value if hasattr(case.status, "value") else str(case.status)).upper(),
            current_node="normalize",
            input_payload=input_payload,
            forced_from_run_id=forced_from,
            requested_by_user_id=principal.user_id if principal else None,
            requested_by_session_id=principal.session_id if principal else None,
        )
        db.add(run)
        db.flush()
        db.add(AgentBudget(
            graph_run_id=run.id,
            case_id=case_id,
            max_agent_runs=settings.agent_max_runs_per_case,
            max_llm_calls=settings.agent_max_llm_calls_per_case,
            max_tool_calls=settings.agent_max_tool_calls_per_case,
            max_probe_calls=settings.agent_max_probe_calls_per_case,
            max_replan_count=settings.agent_max_replan_count,
            max_runtime_seconds=settings.agent_max_runtime_seconds,
            max_target_devices=settings.agent_max_target_devices,
        ))
        agent_task_service.create(
            db,
            graph_run_id=run.id,
            case_id=case_id,
            task_type="deterministic",
            graph_node="normalize",
            goal="Normalize case state and establish graph execution context",
            idempotency_key="normalize:0",
            created_by="graph_service",
        )
        case_timeline_service.append(
            db, case_id=case_id, graph_run_id=run.id, event_type="graph_run", title="Agent graph accepted",
            actor_type="human" if principal else "system", actor_id=str(principal.user_id) if principal else "system",
            idempotency_key=f"graph-accepted:{run.id}", payload={"graph_version": GRAPH_VERSION, "forced_from": forced_from},
        )
        security_audit_service.append(
            db,
            event_type="agent_graph.force_restart" if force_restart else "agent_graph.accepted",
            outcome="success",
            actor_user_id=principal.user_id if principal else None,
            actor_session_id=principal.session_id if principal else None,
            target_type="agent_graph_run",
            target_id=run.id,
            details={"case_id": case_id, "forced_from_run_id": forced_from},
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            active = db.query(AgentGraphRun).filter(
                AgentGraphRun.case_id == case_id,
                AgentGraphRun.status.in_(ACTIVE_GRAPH_STATUSES),
            ).order_by(AgentGraphRun.created_at.desc()).first()
            if active:
                return active, True
            raise
        db.refresh(run)
        return run, False

    @staticmethod
    def view(run: AgentGraphRun, *, already_running: bool = False) -> dict[str, Any]:
        return {
            "case_id": int(run.case_id),
            "status": "running" if already_running else "accepted",
            "execution_mode": "async",
            "graph_run_id": run.id,
            "current_state": run.current_state,
            "current_node": run.current_node,
            "queued": run.status == "queued",
            "already_running": already_running,
            "message": "Agent graph already running" if already_running else "Agent graph execution accepted",
            "legacy_result": None,
            "agent_run_ids": [],
            "claim_ids": [],
            "remediation_plan_id": None,
        }


graph_service = GraphService()
