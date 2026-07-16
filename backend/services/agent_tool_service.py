from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from models.agent_graph import AgentMessage, AgentTask, AgentToolCall
from models.agenticops import CaseRecord, EvidenceItem, EvidenceType
from observability.metrics import metrics_registry
from orchestration.graph_contracts import EvidenceRequest
from policies.guard import policy_guard
from probes.gateway import probe_gateway
from probes.schemas import ProbeRequest
from services.agent_budget_service import agent_budget_service
from services.case_timeline_service import case_timeline_service
from tools.base import ToolRequest
from tools.registry import tool_registry


class AgentToolRejected(RuntimeError):
    pass


class AgentToolService:
    def execute_probe(
        self,
        db: Session,
        *,
        task: AgentTask,
        request_payload: dict[str, Any],
        credential_id: int,
        agent_run_id: int | None = None,
        call_index: int = 0,
    ) -> tuple[AgentToolCall, EvidenceItem | None]:
        request = EvidenceRequest.model_validate(request_payload)
        spec = tool_registry.get(request.probe_id)
        if spec is None:
            raise AgentToolRejected("unregistered_tool")
        selectable, selection_errors = tool_registry.validate_agent_selection(spec, request.target.model_dump())
        if not selectable:
            raise AgentToolRejected(",".join(selection_errors))
        agent_budget_service.consume(db, task.graph_run_id, "tool_calls")
        agent_budget_service.consume(db, task.graph_run_id, "probe_calls")
        agent_budget_service.register_target(db, task.graph_run_id, request.target.netbox_device_id)
        tool_request = ToolRequest(
            tool_id=request.probe_id,
            params=request.parameters,
            target=request.target.model_dump(),
            mode="observe",
            requested_by=f"agent_task:{task.id}",
            case_id=task.case_id,
        )
        case = db.query(CaseRecord).filter(CaseRecord.id == task.case_id).one()
        decision = policy_guard.check(tool_request, case=case, db=db)
        idempotency_key = f"task:{task.id}:probe:{call_index}:{request.probe_id}"
        existing = db.query(AgentToolCall).filter(
            AgentToolCall.graph_run_id == task.graph_run_id,
            AgentToolCall.idempotency_key == idempotency_key,
        ).first()
        if existing is not None:
            evidence = db.query(EvidenceItem).filter(EvidenceItem.tool_call_id == existing.id).first()
            return existing, evidence
        call = AgentToolCall(
            graph_run_id=task.graph_run_id,
            case_id=task.case_id,
            task_id=task.id,
            agent_run_id=agent_run_id,
            tool_id=request.probe_id,
            mode="observe",
            request_payload=request.model_dump(mode="json"),
            policy_decision=decision.to_dict(),
            status="running" if decision.allowed else "rejected",
            idempotency_key=idempotency_key,
        )
        db.add(call)
        db.flush()
        metrics_registry.increment("agent_tool_call_total", tool_id=request.probe_id, status=call.status)
        if not decision.allowed:
            call.finished_at = datetime.now(timezone.utc)
            call.error_message = decision.blocked_reason
            metrics_registry.increment("agent_tool_call_failures_total", tool_id=request.probe_id, reason=decision.blocked_reason or "rejected")
            db.flush()
            raise AgentToolRejected(decision.blocked_reason or "policy_rejected")
        started = datetime.now(timezone.utc)
        result = probe_gateway.run(
            db,
            ProbeRequest(
                probe_id=request.probe_id,
                netbox_device_id=request.target.netbox_device_id,
                credential_id=credential_id,
                parameters=request.parameters,
            ),
        )
        call.finished_at = datetime.now(timezone.utc)
        call.duration_ms = int((call.finished_at - started).total_seconds() * 1000)
        call.status = "completed" if result.status == "succeeded" else result.status
        call.result_payload = result.model_dump(mode="json")
        if result.status != "succeeded" or result.evidence is None:
            call.error_message = result.error_code or "probe_failed"
            metrics_registry.increment("agent_tool_call_failures_total", tool_id=request.probe_id, reason=call.error_message)
            db.flush()
            return call, None
        evidence = EvidenceItem(
            case_id=task.case_id,
            task_id=task.id,
            tool_call_id=call.id,
            probe_run_id=result.run_id,
            evidence_type=EvidenceType.COMMAND_OUTPUT,
            source_system="probe_gateway",
            source_ref=f"probe_run:{result.run_id}",
            occurred_at=result.evidence.collected_at,
            collected_at=result.evidence.collected_at,
            freshness_seconds=0,
            confidence=1.0,
            summary=request.reason,
            payload=result.evidence.model_dump(mode="json"),
        )
        db.add(evidence)
        db.flush()
        correlation_id = str(uuid.uuid4())
        db.add(AgentMessage(
            graph_run_id=task.graph_run_id,
            case_id=task.case_id,
            task_id=task.id,
            sender_type="probe",
            sender_id=request.probe_id,
            receiver_type="agent",
            receiver_id=task.assigned_agent_type or "diagnostic",
            message_type="evidence_response",
            content={"evidence_id": evidence.id, "probe_run_id": result.run_id, "status": result.status},
            artifact_refs=[{"type": "evidence", "id": evidence.id}],
            correlation_id=correlation_id,
        ))
        case_timeline_service.append(
            db,
            case_id=task.case_id,
            graph_run_id=task.graph_run_id,
            task_id=task.id,
            event_type="evidence",
            title=f"Evidence collected: {request.probe_id}",
            actor_type="probe",
            actor_id=request.probe_id,
            correlation_id=correlation_id,
            idempotency_key=f"evidence:{call.id}",
            payload={"evidence_id": evidence.id, "tool_call_id": call.id, "probe_run_id": result.run_id},
        )
        metrics_registry.increment("agent_message_total", message_type="evidence_response")
        db.flush()
        return call, evidence


agent_tool_service = AgentToolService()
