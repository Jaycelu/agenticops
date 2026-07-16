from __future__ import annotations

from sqlalchemy.orm import Session

from config.settings import settings
from models.agent_graph import AgentBudget, AgentTask, CaseHypothesis
from datetime import datetime, timezone

from models.agenticops import EvidenceItem
from orchestration.graph_contracts import SupervisorDecision, SupervisorTaskDecision, SupervisorTransition
from observability.metrics import metrics_registry


ACTIVE_TASKS = {"pending", "ready", "running", "waiting_evidence", "waiting_agent", "waiting_human"}


class CaseSupervisor:
    def decide(self, db: Session, graph_run) -> SupervisorDecision:
        tasks = db.query(AgentTask).filter(AgentTask.graph_run_id == graph_run.id).all()
        active_non_supervisor = [item for item in tasks if item.graph_node != "supervisor" and item.status in ACTIVE_TASKS]
        if active_non_supervisor:
            return SupervisorDecision(decision="wait_agents", reason="assigned tasks are still active")
        completed_nodes = [item.graph_node for item in tasks if item.status == "completed"]
        if "evidence_collection" not in completed_nodes:
            return SupervisorDecision(
                decision="collect_more_evidence",
                reason="initial runtime evidence has not been collected",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "evidence_collecting"}),
                next_tasks=[SupervisorTaskDecision(task_type="evidence_collection", graph_node="evidence_collection", goal="Collect initial read-only runtime evidence")],
            )
        diagnostic_tasks = [item for item in tasks if item.graph_node == "diagnostic" and item.status == "completed"]
        if not diagnostic_tasks:
            return SupervisorDecision(
                decision="run_diagnostics",
                reason="no diagnostic round has completed",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "diagnosing"}),
                next_tasks=[
                    SupervisorTaskDecision(task_type="agent", graph_node="historical", goal="Retrieve relevant operational memory", assigned_agent_type="historical_analysis", priority=90),
                    SupervisorTaskDecision(task_type="agent", graph_node="diagnostic", goal="Generate falsifiable root-cause hypotheses", assigned_agent_type="insight_analysis", priority=100),
                ],
            )
        latest = max(diagnostic_tasks, key=lambda item: (item.insight_round, item.id))
        requests = list((latest.output_payload or {}).get("next_evidence_requests") or [])
        request_task_key = f"evidence_after_round_{latest.insight_round}"
        requested = any(item.idempotency_key == request_task_key for item in tasks)
        if requests and not requested:
            return SupervisorDecision(
                decision="collect_more_evidence",
                reason="top hypotheses still have validated evidence gaps",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "evidence_collecting"}),
                next_tasks=[SupervisorTaskDecision(
                    task_type="probe",
                    graph_node="evidence_collection",
                    goal="Execute validated read-only evidence requests",
                    input_payload={"requests": requests, "next_insight_round": latest.insight_round + 1, "idempotency_key": request_task_key},
                    priority=80,
                )],
            )
        if requests and requested:
            request_task = next(item for item in tasks if item.idempotency_key == request_task_key)
            next_round_exists = any(item.graph_node == "diagnostic" and item.insight_round > latest.insight_round for item in tasks)
            if request_task.status == "completed" and not next_round_exists:
                return SupervisorDecision(
                    decision="run_diagnostics",
                    reason="new evidence is available; rerun diagnosis",
                    state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "diagnosing"}),
                    next_tasks=[SupervisorTaskDecision(
                        task_type="agent", graph_node="diagnostic", goal="Re-evaluate hypotheses with new evidence",
                        assigned_agent_type="insight_analysis", input_payload={"insight_round": latest.insight_round + 1},
                    )],
                )
        critic_tasks = [item for item in tasks if item.graph_node == "critic" and item.status == "completed" and item.insight_round == latest.insight_round]
        if not critic_tasks:
            return SupervisorDecision(
                decision="run_critic",
                reason="latest hypothesis round has not been falsified by an independent critic",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "hypothesis_review"}),
                next_tasks=[SupervisorTaskDecision(task_type="agent", graph_node="critic", goal="Search for contradicting evidence and simpler explanations", assigned_agent_type="diagnostic_critic", input_payload={"insight_round": latest.insight_round})],
            )
        critic = critic_tasks[-1]
        hypotheses = db.query(CaseHypothesis).filter(
            CaseHypothesis.graph_run_id == graph_run.id,
            CaseHypothesis.insight_round == latest.insight_round,
        ).all()
        confirmed = [item for item in hypotheses if self._confirmable(db, item, critic.output_payload or {})]
        if not confirmed:
            metrics_registry.increment("human_escalation_total", reason="root_cause_unconfirmed")
            return SupervisorDecision(
                decision="escalate",
                reason="no hypothesis satisfies configured confirmation and critic thresholds",
                stop_reason="root_cause_unconfirmed",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "escalated"}),
            )
        plan_done = any(item.graph_node == "plan_candidate" and item.status == "completed" for item in tasks)
        if not plan_done:
            confirmed[0].status = "confirmed"
            metrics_registry.increment("hypothesis_confirmed_total")
            db.flush()
            return SupervisorDecision(
                decision="plan",
                reason=f"hypothesis {confirmed[0].hypothesis_code} passed arbitration",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "planning"}),
                next_tasks=[SupervisorTaskDecision(task_type="agent", graph_node="plan_candidate", goal="Generate a non-executing remediation plan candidate", assigned_agent_type="autonomous_remediation")],
            )
        safety_tasks = [item for item in tasks if item.graph_node == "safety_review" and item.status == "completed"]
        safety_done = bool(safety_tasks)
        if not safety_done:
            return SupervisorDecision(
                decision="safety_review",
                reason="plan candidate requires independent safety review",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "safety_review"}),
                next_tasks=[SupervisorTaskDecision(task_type="agent", graph_node="safety_review", goal="Review plan safety without executing it", assigned_agent_type="safety_critic")],
            )
        if str((safety_tasks[-1].output_payload or {}).get("decision")) == "rejected":
            return SupervisorDecision(
                decision="escalate",
                reason="independent safety critic rejected the plan candidate",
                stop_reason="safety_critic_rejected",
                state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "escalated"}),
            )
        return SupervisorDecision(
            decision="observe_only_stop",
            reason="safety review completed; production changes remain disabled",
            stop_reason="observe_only_stop",
            state_transition=SupervisorTransition.model_validate({"from": graph_run.current_state.lower(), "to": "observing"}),
        )

    @staticmethod
    def _confirmable(db: Session, hypothesis: CaseHypothesis, critic_output: dict) -> bool:
        if float(hypothesis.confidence) < settings.hypothesis_confirm_confidence:
            return False
        if str(critic_output.get("decision")) == "reject":
            return False
        if len(hypothesis.contradicting_evidence_ids or []) > settings.hypothesis_max_high_weight_contradictions:
            return False
        support = list(hypothesis.supporting_evidence_ids or [])
        if not support:
            return False
        evidence = db.query(EvidenceItem).filter(EvidenceItem.id.in_(support)).all()
        if len(evidence) != len(set(support)):
            return False
        now = datetime.now(timezone.utc)
        for item in evidence:
            collected = item.collected_at
            if collected and collected.tzinfo is None:
                collected = collected.replace(tzinfo=timezone.utc)
            if not collected or (now - collected).total_seconds() > settings.hypothesis_evidence_max_age_seconds:
                return False
        sources = {item.source_system for item in evidence}
        direct = any((item.evidence_type.value if hasattr(item.evidence_type, "value") else str(item.evidence_type)) == "command_output" for item in evidence)
        return direct or len(sources) >= 2


case_supervisor = CaseSupervisor()
