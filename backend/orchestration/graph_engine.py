from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agents.alert_triage_agent import alert_triage_agent
from agents.autonomous_remediation_agent import autonomous_remediation_agent
from agents.diagnostic_critic_agent import diagnostic_critic_agent
from agents.historical_analysis_agent import historical_analysis_agent
from agents.insight_analysis_agent import insight_analysis_agent
from agents.safety_critic_agent import safety_critic_agent
from agents.schemas import AgentExecutionContext
from config.settings import settings
from engines.case_orchestrator import case_orchestrator
from models.agent_graph import AgentBudget, AgentGraphRun, AgentMessage, AgentTask, CaseHypothesis
from models.agenticops import AgentClaim, AgentRun, CaseRecord, EvidenceItem, MemoryEntry, RemediationPlan
from orchestration.agent_runner import agent_runner
from orchestration.case_supervisor import case_supervisor
from orchestration.graph_contracts import EvidenceRequest
from services.agent_checkpoint_service import agent_checkpoint_service
from services.agent_budget_service import BudgetExhausted
from services.agent_task_service import agent_task_service
from services.agent_tool_service import AgentToolRejected, agent_tool_service
from services.case_state_service import case_state_service
from services.case_timeline_service import case_timeline_service


AGENTS = {
    "alert_triage": alert_triage_agent,
    "historical_analysis": historical_analysis_agent,
    "insight_analysis": insight_analysis_agent,
    "diagnostic_critic": diagnostic_critic_agent,
    "autonomous_remediation": autonomous_remediation_agent,
    "safety_critic": safety_critic_agent,
}


class CaseGraphEngine:
    async def execute_task(self, db: Session, graph_run: AgentGraphRun, task: AgentTask) -> None:
        correlation_id = str(uuid.uuid4())
        graph_run.status = "running"
        graph_run.started_at = graph_run.started_at or datetime.now(timezone.utc)
        graph_run.current_node = task.graph_node
        agent_task_service.transition(db, task, "running")
        case_timeline_service.append(
            db, case_id=task.case_id, graph_run_id=graph_run.id, task_id=task.id,
            event_type="agent_task", title=f"Task running: {task.graph_node}", actor_type="worker",
            idempotency_key=f"task-running:{task.id}:{task.attempt_count}", correlation_id=correlation_id,
            payload={"attempt": task.attempt_count},
        )
        try:
            if task.graph_node == "normalize":
                self._normalize(db, graph_run, task, correlation_id)
            elif task.graph_node == "supervisor":
                self._supervise(db, graph_run, task, correlation_id)
            elif task.graph_node == "evidence_collection":
                await self._collect_evidence(db, graph_run, task, correlation_id)
            elif task.graph_node in {"triage", "historical", "diagnostic", "critic", "plan_candidate", "safety_review"}:
                await self._run_agent_node(db, graph_run, task, correlation_id)
            else:
                raise ValueError(f"unknown graph node: {task.graph_node}")
            if task.status == "running":
                agent_task_service.transition(db, task, "completed", output=task.output_payload or {})
            if task.status == "completed" and task.graph_node != "supervisor" and graph_run.status not in {"completed", "failed", "cancelled", "budget_exhausted", "waiting_human"}:
                self._schedule_supervisor(db, graph_run, parent_task_id=task.id)
            agent_checkpoint_service.create(db, graph_run, {"last_task_id": task.id, "correlation_id": correlation_id})
            db.commit()
        except BudgetExhausted as exc:
            db.rollback()
            task = db.query(AgentTask).filter(AgentTask.id == task.id).with_for_update().one()
            graph_run = db.query(AgentGraphRun).filter(AgentGraphRun.id == graph_run.id).with_for_update().one()
            task.status = "failed"
            task.error_message = f"budget_exhausted:{exc}"
            task.finished_at = datetime.now(timezone.utc)
            graph_run.status = "budget_exhausted"
            graph_run.stop_reason = f"budget_exhausted:{exc}"
            graph_run.finished_at = datetime.now(timezone.utc)
            budget = db.query(AgentBudget).filter(AgentBudget.graph_run_id == graph_run.id).with_for_update().one()
            budget.exhausted = True
            budget.exhausted_reason = str(exc)
            case_state_service.transition(
                db, case_id=task.case_id, to_state="escalated", trigger_type="budget", trigger_id=graph_run.id,
                reason=graph_run.stop_reason, idempotency_key=f"state:{graph_run.id}:budget-exhausted",
                graph_run_id=graph_run.id, task_id=task.id, correlation_id=correlation_id,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            task = db.query(AgentTask).filter(AgentTask.id == task.id).with_for_update().one()
            graph_run = db.query(AgentGraphRun).filter(AgentGraphRun.id == graph_run.id).with_for_update().one()
            if task.attempt_count < task.max_attempts:
                task.status = "ready"
                task.error_message = f"{type(exc).__name__}: {str(exc)[:2000]}"
            else:
                task.status = "failed"
                task.finished_at = datetime.now(timezone.utc)
                graph_run.status = "failed"
                graph_run.error_message = f"{type(exc).__name__}: {str(exc)[:2000]}"
                graph_run.finished_at = datetime.now(timezone.utc)
            case_timeline_service.append(
                db, case_id=task.case_id, graph_run_id=graph_run.id, task_id=task.id,
                event_type="agent_task", title=f"Task error: {task.graph_node}", actor_type="worker",
                idempotency_key=f"task-error:{task.id}:{task.attempt_count}", correlation_id=correlation_id,
                payload={"error_type": type(exc).__name__, "retry": task.status == "ready"},
            )
            db.commit()

    def _normalize(self, db: Session, graph_run: AgentGraphRun, task: AgentTask, correlation_id: str) -> None:
        case = db.query(CaseRecord).filter(CaseRecord.id == task.case_id).one()
        current = case.status.value if hasattr(case.status, "value") else str(case.status)
        if current in {"new", "open"}:
            case_state_service.transition(
                db, case_id=case.id, to_state="normalized", trigger_type="graph", trigger_id=graph_run.id,
                reason="case normalized for durable graph execution", idempotency_key=f"state:{graph_run.id}:normalized",
                graph_run_id=graph_run.id, task_id=task.id, correlation_id=correlation_id,
            )
        graph_run.current_state = "NORMALIZED"
        task.output_payload = {"normalized": True}
        agent_task_service.create(
            db, graph_run_id=graph_run.id, case_id=case.id, task_type="agent", graph_node="triage",
            goal="Deterministically triage priority and diagnostic scope", idempotency_key="triage:0",
            assigned_agent_type="alert_triage", parent_task_id=task.id,
        )

    def _supervise(self, db: Session, graph_run: AgentGraphRun, task: AgentTask, correlation_id: str) -> None:
        decision = case_supervisor.decide(db, graph_run)
        task.output_payload = decision.model_dump(by_alias=True, mode="json")
        db.add(AgentMessage(
            graph_run_id=graph_run.id, case_id=graph_run.case_id, task_id=task.id,
            sender_type="supervisor", sender_id="case_supervisor", receiver_type="graph", receiver_id=graph_run.id,
            message_type="safety_review" if decision.decision == "safety_review" else "task_assignment",
            content=task.output_payload, artifact_refs=[], correlation_id=correlation_id,
        ))
        case_timeline_service.append(
            db, case_id=graph_run.case_id, graph_run_id=graph_run.id, task_id=task.id,
            event_type="supervisor_decision", title=f"Supervisor: {decision.decision}", actor_type="supervisor",
            idempotency_key=f"supervisor-decision:{task.id}", correlation_id=correlation_id,
            payload=task.output_payload,
        )
        if decision.state_transition:
            target = decision.state_transition.to_state
            case_state_service.transition(
                db, case_id=graph_run.case_id, to_state=target, trigger_type="supervisor", trigger_id="case_supervisor",
                reason=decision.reason, idempotency_key=f"state:{graph_run.id}:{task.id}:{target}",
                graph_run_id=graph_run.id, task_id=task.id, correlation_id=correlation_id,
            )
            graph_run.current_state = target.upper()
        for index, next_task in enumerate(decision.next_tasks):
            explicit_key = (next_task.input_payload or {}).get("idempotency_key")
            round_no = int((next_task.input_payload or {}).get("insight_round") or (next_task.input_payload or {}).get("next_insight_round") or 0)
            agent_task_service.create(
                db, graph_run_id=graph_run.id, case_id=graph_run.case_id,
                task_type=next_task.task_type, graph_node=next_task.graph_node, goal=next_task.goal,
                assigned_agent_type=next_task.assigned_agent_type,
                assigned_agent_name=AGENTS.get(next_task.assigned_agent_type).agent_name if next_task.assigned_agent_type in AGENTS else None,
                input_payload=next_task.input_payload, priority=next_task.priority,
                parent_task_id=task.id, insight_round=round_no,
                idempotency_key=explicit_key or f"{next_task.graph_node}:{task.id}:{index}:{round_no}",
            )
        if decision.stop_reason:
            graph_run.stop_reason = decision.stop_reason
            graph_run.status = "completed" if decision.decision == "observe_only_stop" else "failed"
            graph_run.finished_at = datetime.now(timezone.utc)

    async def _collect_evidence(self, db: Session, graph_run: AgentGraphRun, task: AgentTask, correlation_id: str) -> None:
        requests = list((task.input_payload or {}).get("requests") or [])
        if not requests:
            case = db.query(CaseRecord).filter(CaseRecord.id == task.case_id).one()
            params = graph_run.input_payload or {}
            runtime = await case_orchestrator._collect_runtime_context(
                db, case=case, base_name=params.get("base_name"), log_query=params.get("log_query"),
                time_range=params.get("time_range") or "-15m,now", log_limit=int(params.get("log_limit") or 200),
                credential_id=params.get("credential_id"),
            )
            task.output_payload = {"runtime": runtime, "evidence_ids": [item.id for item in db.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).all()]}
            return
        credential_id = (graph_run.input_payload or {}).get("credential_id")
        if not credential_id:
            agent_task_service.transition(db, task, "waiting_human", error="credential_required_for_probe")
            graph_run.status = "waiting_human"
            graph_run.current_node = "human_gate"
            db.add(AgentMessage(
                graph_run_id=graph_run.id, case_id=task.case_id, task_id=task.id,
                sender_type="supervisor", sender_id="case_supervisor", receiver_type="human", receiver_id=None,
                message_type="human_handoff", content={"reason": "credential_required_for_probe"}, artifact_refs=[], correlation_id=correlation_id,
            ))
            return
        evidence_ids = []
        for index, raw in enumerate(requests[: settings.agent_max_tool_calls_per_run]):
            request = EvidenceRequest.model_validate(raw)
            _call, evidence = agent_tool_service.execute_probe(
                db, task=task, request_payload=request.model_dump(mode="json"), credential_id=int(credential_id), call_index=index,
            )
            if evidence:
                evidence_ids.append(evidence.id)
        task.output_payload = {"evidence_ids": evidence_ids, "request_count": len(requests)}

    async def _run_agent_node(self, db: Session, graph_run: AgentGraphRun, task: AgentTask, correlation_id: str) -> None:
        case = db.query(CaseRecord).filter(CaseRecord.id == task.case_id).one()
        context = self._context(db, graph_run, case, task.insight_round)
        agent_key = task.assigned_agent_type or {
            "triage": "alert_triage", "historical": "historical_analysis", "diagnostic": "insight_analysis",
            "critic": "diagnostic_critic", "plan_candidate": "autonomous_remediation", "safety_review": "safety_critic",
        }[task.graph_node]
        agent = AGENTS[agent_key]
        if task.graph_node == "critic":
            context.runtime["hypotheses"] = [self._hypothesis_view(item) for item in db.query(CaseHypothesis).filter(
                CaseHypothesis.graph_run_id == graph_run.id, CaseHypothesis.insight_round == task.insight_round,
            ).all()]
        run, claim = await agent_runner.execute(
            db, case, agent, context, graph_run_id=graph_run.id, task_id=task.id,
        )
        task.output_payload = run.output_payload or {}
        case_timeline_service.append(
            db, case_id=case.id, graph_run_id=graph_run.id, task_id=task.id,
            event_type="critic" if task.graph_node == "critic" else "agent_run",
            title=f"{agent.agent_name} completed", actor_type="agent", actor_id=agent_key,
            idempotency_key=f"agent-run:{run.id}", correlation_id=correlation_id,
            payload={"agent_run_id": run.id, "claim_id": claim.id, "claim_type": claim.claim_type, "confidence": claim.confidence},
        )
        if task.graph_node == "triage":
            case.priority = str((run.output_payload or {}).get("priority") or case.priority)
            case_state_service.transition(
                db, case_id=case.id, to_state="triaged", trigger_type="agent", trigger_id=agent_key,
                reason="triage agent completed", idempotency_key=f"state:{graph_run.id}:triaged",
                graph_run_id=graph_run.id, agent_run_id=run.id, task_id=task.id, correlation_id=correlation_id,
            )
            graph_run.current_state = "TRIAGED"
        elif task.graph_node == "diagnostic":
            requests = self._persist_hypotheses(db, graph_run, task, run.output_payload or {}, correlation_id)
            task.output_payload = {**(run.output_payload or {}), "next_evidence_requests": requests}
        elif task.graph_node == "critic":
            decision = str((run.output_payload or {}).get("decision") or "reject")
            for hypothesis in db.query(CaseHypothesis).filter(
                CaseHypothesis.graph_run_id == graph_run.id, CaseHypothesis.insight_round == task.insight_round,
            ).all():
                hypothesis.critic_decision = decision
                hypothesis.critic_payload = run.output_payload or {}
                if decision == "reject":
                    hypothesis.status = "rejected"
                elif decision == "revise":
                    hypothesis.status = "weakened"
                else:
                    hypothesis.status = "supported"
        elif task.graph_node == "plan_candidate":
            plan = case_orchestrator._create_remediation_plan(db, case, run, claim, run.output_payload or {})
            task.output_payload = {**(run.output_payload or {}), "remediation_plan_id": plan.id}
        elif task.graph_node == "safety_review":
            decision = str((run.output_payload or {}).get("decision") or "rejected")
            plan = db.query(RemediationPlan).filter(RemediationPlan.case_id == case.id).order_by(RemediationPlan.id.desc()).first()
            case_orchestrator._apply_safety_critic_decision(plan, run.output_payload or {}, decision)

    def _context(self, db: Session, graph_run: AgentGraphRun, case: CaseRecord, insight_round: int) -> AgentExecutionContext:
        evidence = db.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).order_by(EvidenceItem.id.asc()).all()
        claims = db.query(AgentClaim, AgentRun).join(AgentRun, AgentRun.id == AgentClaim.agent_run_id).filter(
            AgentClaim.case_id == case.id, AgentRun.graph_run_id == graph_run.id,
        ).order_by(AgentClaim.id.asc()).all()
        runtime_task = db.query(AgentTask).filter(
            AgentTask.graph_run_id == graph_run.id, AgentTask.graph_node == "evidence_collection", AgentTask.status == "completed",
        ).order_by(AgentTask.id.desc()).first()
        runtime = dict((runtime_task.output_payload or {}).get("runtime") or {}) if runtime_task else {}
        runtime["similar_cases"] = case_orchestrator._find_similar_closed_cases(db, case)
        return AgentExecutionContext(
            case_id=case.id, case_code=case.case_code, title=case.title, summary=case.summary or "",
            source_system=case.source_event.source_system if case.source_event else "manual",
            source_payload=case.source_event.raw_payload if case.source_event else {},
            normalized_payload=case.source_event.normalized_payload if case.source_event else {},
            site_id=case.site_id, netbox_device_id=case.netbox_device_id, device_ip=case.device_ip, host=case.host,
            evidence_items=[{
                "id": item.id, "evidence_type": item.evidence_type.value if hasattr(item.evidence_type, "value") else str(item.evidence_type),
                "source_system": item.source_system, "summary": item.summary, "payload": item.payload or {}, "collected_at": item.collected_at,
            } for item in evidence],
            prior_claims=[{
                "id": claim.id, "claim_type": claim.claim_type, "confidence": claim.confidence,
                "gaps": claim.gaps or [], "metadata": claim.claim_metadata or {}, "output_payload": run.output_payload or {},
            } for claim, run in claims],
            memory_hits=[{"id": item.id, "title": item.title, "confidence": item.confidence, "content": item.content or {}}
                         for item in db.query(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(5).all()],
            runtime=runtime, insight_round=insight_round,
        )

    def _persist_hypotheses(self, db: Session, graph_run: AgentGraphRun, task: AgentTask, output: dict, correlation_id: str) -> list[dict]:
        valid_evidence = {item.id for item in db.query(EvidenceItem.id).filter(EvidenceItem.case_id == task.case_id).all()}
        requests: list[dict] = []
        for index, raw in enumerate(output.get("hypotheses") or []):
            supporting = [int(item) for item in raw.get("supporting_evidence_ids") or [] if int(item) in valid_evidence]
            contradicting = [int(item) for item in raw.get("contradicting_evidence_ids") or [] if int(item) in valid_evidence]
            hypothesis_code = str(raw.get("hypothesis_code") or raw.get("id") or f"h{index + 1}")
            next_requests = []
            for candidate in raw.get("next_probe_requests") or []:
                try:
                    parsed = EvidenceRequest.model_validate(candidate).model_dump(mode="json")
                    next_requests.append(parsed)
                    requests.append(parsed)
                except Exception:
                    continue
            row = CaseHypothesis(
                graph_run_id=graph_run.id, case_id=task.case_id, task_id=task.id,
                hypothesis_code=hypothesis_code, cause_code=str(raw.get("cause_code") or hypothesis_code),
                cause=str(raw.get("cause") or "unknown"), confidence=max(0.0, min(1.0, float(raw.get("confidence") or 0))),
                supporting_evidence_ids=supporting, contradicting_evidence_ids=contradicting,
                missing_evidence=list(raw.get("missing_evidence") or []), next_probe_requests=next_requests,
                status=str(raw.get("status") or "proposed"), insight_round=task.insight_round,
            )
            db.add(row)
            db.flush()
            db.add(AgentMessage(
                graph_run_id=graph_run.id, case_id=task.case_id, task_id=task.id,
                sender_type="agent", sender_id="insight_analysis", receiver_type="supervisor", receiver_id="case_supervisor",
                message_type="hypothesis", content=self._hypothesis_view(row),
                artifact_refs=[{"type": "hypothesis", "id": row.id}], correlation_id=correlation_id,
            ))
            case_timeline_service.append(
                db, case_id=task.case_id, graph_run_id=graph_run.id, task_id=task.id,
                event_type="hypothesis", title=f"Hypothesis: {row.cause_code}", actor_type="agent", actor_id="insight_analysis",
                idempotency_key=f"hypothesis:{row.id}", correlation_id=correlation_id, payload=self._hypothesis_view(row),
            )
        return requests

    @staticmethod
    def _hypothesis_view(item: CaseHypothesis) -> dict[str, Any]:
        return {
            "id": item.id, "hypothesis_code": item.hypothesis_code, "cause_code": item.cause_code,
            "cause": item.cause, "confidence": item.confidence,
            "supporting_evidence_ids": item.supporting_evidence_ids or [],
            "contradicting_evidence_ids": item.contradicting_evidence_ids or [],
            "missing_evidence": item.missing_evidence or [], "next_probe_requests": item.next_probe_requests or [],
            "status": item.status, "insight_round": item.insight_round,
        }

    def _schedule_supervisor(self, db: Session, graph_run: AgentGraphRun, parent_task_id: int) -> AgentTask:
        sequence = db.query(AgentTask).filter(AgentTask.graph_run_id == graph_run.id, AgentTask.graph_node == "supervisor").count()
        return agent_task_service.create(
            db, graph_run_id=graph_run.id, case_id=graph_run.case_id, task_type="supervisor", graph_node="supervisor",
            goal="Arbitrate current graph state and schedule bounded next work",
            idempotency_key=f"supervisor:{sequence + 1}:{parent_task_id}", parent_task_id=parent_task_id,
        )


case_graph_engine = CaseGraphEngine()
