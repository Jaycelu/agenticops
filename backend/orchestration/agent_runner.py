from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from agents.schemas import AgentExecutionContext
from models.agenticops import AgentClaim, AgentRun, AgentRunStatus, CaseRecord, ClaimStatus
from services.agent_budget_service import agent_budget_service


class AgentRunner:
    async def execute(
        self,
        db: Session,
        case: CaseRecord,
        agent: Any,
        context: AgentExecutionContext,
        *,
        graph_run_id: str | None = None,
        task_id: int | None = None,
    ) -> tuple[AgentRun, AgentClaim]:
        if graph_run_id:
            agent_budget_service.consume(db, graph_run_id, "agent_runs")
            agent_type_value = agent.agent_type.value if hasattr(agent.agent_type, "value") else str(agent.agent_type)
            if agent_type_value == "insight_analysis":
                agent_budget_service.consume(db, graph_run_id, "llm_calls")
        started_at = datetime.utcnow()
        claim_meta = {"insight_round": context.insight_round, "harness_trace": list(context.harness_trace)}
        run = AgentRun(
            case_id=case.id,
            graph_run_id=graph_run_id,
            task_id=task_id,
            agent_type=agent.agent_type,
            agent_name=agent.agent_name,
            status=AgentRunStatus.RUNNING,
            input_payload={
                "case_id": case.id,
                "evidence_count": len(context.evidence_items),
                "memory_hits": len(context.memory_hits),
                "evidence_bundle": context.evidence_bundle,
                "episode_goal": context.episode_goal,
                "insight_round": context.insight_round,
            },
            started_at=started_at,
        )
        db.add(run)
        db.flush()
        try:
            decision = await agent.run(context)
            finished_at = datetime.utcnow()
            run.status = AgentRunStatus.COMPLETED
            run.finished_at = finished_at
            run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            run.output_payload = decision.output_payload
            merged_meta = {**decision.metadata, **claim_meta}
            if decision.next_evidence_requests:
                merged_meta["next_evidence_requests"] = decision.next_evidence_requests
            if decision.cited_evidence_item_ids:
                merged_meta["cited_evidence_item_ids"] = decision.cited_evidence_item_ids
            if decision.stopped_reason:
                merged_meta["stopped_reason"] = decision.stopped_reason
            claim = AgentClaim(
                case_id=case.id,
                agent_run_id=run.id,
                agent_type=agent.agent_type,
                claim_type=decision.claim_type,
                claim_text=decision.claim_text,
                status=ClaimStatus(decision.status),
                confidence=decision.confidence,
                evidence_refs=decision.evidence_refs,
                gaps=decision.gaps,
                claim_metadata=merged_meta,
            )
        except Exception as exc:
            finished_at = datetime.utcnow()
            run.status = AgentRunStatus.FAILED
            run.finished_at = finished_at
            run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            run.error_message = f"{type(exc).__name__}: {str(exc)[:1000]}"
            claim = AgentClaim(
                case_id=case.id,
                agent_run_id=run.id,
                agent_type=agent.agent_type,
                claim_type="agent_failure",
                claim_text=f"{agent.agent_name} 执行失败（{type(exc).__name__}）",
                status=ClaimStatus.REJECTED,
                confidence=0.0,
                evidence_refs=[],
                gaps=[type(exc).__name__],
                claim_metadata=claim_meta,
            )
        db.add(claim)
        db.flush()
        return run, claim


agent_runner = AgentRunner()
