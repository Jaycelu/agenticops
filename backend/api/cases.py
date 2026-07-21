from datetime import datetime, timezone
from typing import Optional

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import func
from sqlalchemy.orm import Session

from audit.service import security_audit_service
from database import get_db
from api.schemas.cases import (
    CaseCreateRequest,
    CaseDetailResponse,
    CaseIntakeRequest,
    CaseListResponse,
    CaseOverviewResponse,
    CasePipelineResponse,
    CaseSummaryResponse,
    EvidenceItemResponse,
    SourceEventResponse,
)
from engines.case_orchestrator import case_orchestrator
from models.agenticops import AgentClaim, AgentRun, CaseRecord, CaseStatus, EvidenceItem, RemediationPlan, SourceEvent
from auth.dependencies import require_permissions
from auth.rbac import Permission
from auth.schemas import Principal
from models.agent_graph import AgentBudget, AgentCheckpoint, AgentGraphRun, AgentMessage, AgentTask, AgentToolCall, CaseHypothesis, CaseTimelineEvent
from orchestration.graph_service import graph_service
from services.case_timeline_service import case_timeline_service

router = APIRouter(prefix="/api/cases", tags=["Case 中心"])


def _to_source_event_response(item: SourceEvent) -> SourceEventResponse:
    return SourceEventResponse(
        id=item.id,
        source_type=item.source_type,
        source_system=item.source_system,
        external_event_id=item.external_event_id,
        dedup_key=item.dedup_key,
        site_id=item.site_id,
        netbox_device_id=item.netbox_device_id,
        device_ip=item.device_ip,
        host=item.host,
        title=item.title,
        severity=item.severity,
        status=item.status.value if hasattr(item.status, "value") else str(item.status),
        occurred_at=item.occurred_at,
        collected_at=item.collected_at,
    )


def _to_case_summary_response(item: CaseRecord) -> CaseSummaryResponse:
    return CaseSummaryResponse(
        id=item.id,
        case_code=item.case_code,
        title=item.title,
        summary=item.summary,
        source_event_id=item.source_event_id,
        site_id=item.site_id,
        netbox_device_id=item.netbox_device_id,
        device_ip=item.device_ip,
        host=item.host,
        priority=item.priority,
        risk_level=item.risk_level,
        status=item.status.value if hasattr(item.status, "value") else str(item.status),
        current_phase=item.current_phase,
        opened_at=item.opened_at,
        last_activity_at=item.last_activity_at,
    )


@router.get("/overview", response_model=CaseOverviewResponse)
async def get_case_overview(db: Session = Depends(get_db)):
    total_cases = db.query(func.count(CaseRecord.id)).scalar() or 0
    open_cases = db.query(func.count(CaseRecord.id)).filter(CaseRecord.status.in_([
        CaseStatus.NEW,
        CaseStatus.NORMALIZED,
        CaseStatus.OPEN,
        CaseStatus.TRIAGED,
        CaseStatus.EVIDENCE_COLLECTING,
        CaseStatus.DIAGNOSING,
        CaseStatus.HYPOTHESIS_REVIEW,
        CaseStatus.PLANNING,
        CaseStatus.SAFETY_REVIEW,
        CaseStatus.AWAITING_APPROVAL,
        CaseStatus.INVESTIGATING,
        CaseStatus.PLANNED,
        CaseStatus.EXECUTING,
        CaseStatus.VERIFYING,
        CaseStatus.OBSERVING,
    ])).scalar() or 0
    executing_cases = db.query(func.count(CaseRecord.id)).filter(CaseRecord.status == CaseStatus.EXECUTING).scalar() or 0
    resolved_cases = db.query(func.count(CaseRecord.id)).filter(CaseRecord.status.in_([CaseStatus.RESOLVED, CaseStatus.CLOSED])).scalar() or 0
    high_risk_cases = db.query(func.count(CaseRecord.id)).filter(CaseRecord.risk_level.in_(["high", "critical"])).scalar() or 0
    phase_rows = db.query(CaseRecord.current_phase, func.count(CaseRecord.id)).group_by(CaseRecord.current_phase).all()
    by_phase = {phase or "unknown": count for phase, count in phase_rows}

    return CaseOverviewResponse(
        total_cases=total_cases,
        open_cases=open_cases,
        executing_cases=executing_cases,
        resolved_cases=resolved_cases,
        high_risk_cases=high_risk_cases,
        by_phase=by_phase,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(
    site_id: Optional[int] = None,
    status: Optional[str] = None,
    current_phase: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(CaseRecord)
    if site_id is not None:
        query = query.filter(CaseRecord.site_id == site_id)
    if status:
        query = query.filter(CaseRecord.status == status)
    if current_phase:
        query = query.filter(CaseRecord.current_phase == current_phase)

    total = query.count()
    items = query.order_by(CaseRecord.opened_at.desc()).offset(skip).limit(limit).all()
    return CaseListResponse(total=total, items=[_to_case_summary_response(item) for item in items])


@router.post(
    "",
    response_model=CaseDetailResponse,
    dependencies=[Depends(require_permissions(Permission.PROBES_RUN.value))],
)
async def create_case(payload: CaseCreateRequest, db: Session = Depends(get_db)):
    case = await case_orchestrator.intake_case(
        db,
        title=payload.title,
        source_type=payload.source_type,
        source_system=payload.source_system,
        dedup_key=payload.dedup_key,
        severity=payload.severity,
        site_id=payload.site_id,
        netbox_device_id=payload.netbox_device_id,
        device_ip=payload.device_ip,
        host=payload.host,
        summary=payload.summary,
        occurred_at=payload.occurred_at,
        raw_payload=payload.raw_payload,
        normalized_payload=payload.normalized_payload,
        case_metadata=payload.case_metadata,
    )
    source_event = case.source_event

    return CaseDetailResponse(
        **_to_case_summary_response(case).model_dump(),
        case_metadata=case.case_metadata or {},
        closed_at=case.closed_at,
        source_event=_to_source_event_response(source_event),
    )


@router.post(
    "/intake",
    response_model=CasePipelineResponse,
    dependencies=[Depends(require_permissions(Permission.PROBES_RUN.value))],
)
async def intake_case(payload: CaseIntakeRequest, db: Session = Depends(get_db)):
    case = await case_orchestrator.intake_case(
        db,
        title=payload.title,
        source_type=payload.source_type,
        source_system=payload.source_system,
        dedup_key=payload.dedup_key,
        severity=payload.severity,
        site_id=payload.site_id,
        netbox_device_id=payload.netbox_device_id,
        device_ip=payload.device_ip,
        host=payload.host,
        summary=payload.summary,
        occurred_at=payload.occurred_at,
        raw_payload=payload.raw_payload,
        normalized_payload=payload.normalized_payload,
        case_metadata=payload.case_metadata,
    )
    if not payload.run_pipeline:
        return CasePipelineResponse(case_id=case.id)
    result = await case_orchestrator.run_case_pipeline(
        db,
        case_id=case.id,
        base_name=payload.base_name,
        log_query=payload.log_query,
        time_range=payload.time_range,
        log_limit=payload.log_limit,
        credential_id=payload.credential_id,
    )
    return CasePipelineResponse(**result)


@router.get("/{case_id}", response_model=CaseDetailResponse)
async def get_case(case_id: int, db: Session = Depends(get_db)):
    item = db.query(CaseRecord).filter(CaseRecord.id == case_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseDetailResponse(
        **_to_case_summary_response(item).model_dump(),
        case_metadata=item.case_metadata or {},
        closed_at=item.closed_at,
        source_event=_to_source_event_response(item.source_event) if item.source_event else None,
    )


@router.get("/{case_id}/evidence", response_model=list[EvidenceItemResponse])
async def list_case_evidence(case_id: int, db: Session = Depends(get_db)):
    case = db.query(CaseRecord.id).filter(CaseRecord.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).order_by(EvidenceItem.created_at.desc()).all()
    return [
        EvidenceItemResponse(
            id=item.id,
            evidence_type=item.evidence_type.value if hasattr(item.evidence_type, "value") else str(item.evidence_type),
            source_system=item.source_system,
            source_ref=item.source_ref,
            fingerprint=item.fingerprint,
            device_ip=item.device_ip,
            host=item.host,
            occurred_at=item.occurred_at,
            collected_at=item.collected_at,
            confidence=float(item.confidence or 0.0),
            summary=item.summary,
            payload=item.payload or {},
        )
        for item in items
    ]


@router.post(
    "/{case_id}/run-agents",
    response_model=CasePipelineResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def run_case_agents(
    case_id: int,
    base_name: Optional[str] = None,
    log_query: Optional[str] = None,
    time_range: str = "-15m,now",
    log_limit: int = Query(200, ge=1, le=1000),
    credential_id: Optional[int] = None,
    force_restart: bool = False,
    wait: bool = False,
    timeout_seconds: int = Query(30, ge=1, le=30),
    principal: Principal = Depends(require_permissions(Permission.PROBES_RUN.value)),
    db: Session = Depends(get_db),
):
    if force_restart and Permission.AGENT_GRAPHS_RESTART.value not in principal.permissions:
        raise HTTPException(status_code=403, detail={"code": "permission_denied", "missing": [Permission.AGENT_GRAPHS_RESTART.value]})
    try:
        run, already_running = graph_service.enqueue(
            db,
            case_id=case_id,
            principal=principal,
            force_restart=force_restart,
            input_payload={
                "base_name": base_name,
                "log_query": log_query,
                "time_range": time_range,
                "log_limit": log_limit,
                "credential_id": credential_id,
            },
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Case not found")
    if wait:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            db.expire_all()
            current = db.query(AgentGraphRun).filter(AgentGraphRun.id == run.id).one()
            if current.status in {"completed", "failed", "cancelled", "timed_out", "budget_exhausted"}:
                payload = graph_service.view(current, already_running=already_running)
                payload["status"] = current.status
                payload["queued"] = False
                return CasePipelineResponse(**payload)
            await asyncio.sleep(0.25)
    return CasePipelineResponse(**graph_service.view(run, already_running=already_running))


def _graph_view(run: AgentGraphRun) -> dict:
    return {
        "graph_run_id": run.id, "case_id": run.case_id, "graph_version": run.graph_version,
        "status": run.status, "current_state": run.current_state, "current_node": run.current_node,
        "stop_reason": run.stop_reason, "error_message": run.error_message,
        "forced_from_run_id": run.forced_from_run_id, "started_at": run.started_at,
        "finished_at": run.finished_at, "created_at": run.created_at, "updated_at": run.updated_at,
    }


@router.post(
    "/{case_id}/graph/resume",
    response_model=CasePipelineResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def resume_case_graph(
    case_id: int,
    credential_id: int = Query(..., ge=1, description="Credential ID for probe execution"),
    principal: Principal = Depends(require_permissions(Permission.PROBES_RUN.value)),
    db: Session = Depends(get_db),
):
    """Resume a graph run stuck in waiting_human by supplying the missing credential.

    Resets the run to queued and all waiting tasks to ready,
    so the next worker poll picks them up. Rejects 409 if no
    waiting_human run or task exists.
    """
    run = db.query(AgentGraphRun).filter(
        AgentGraphRun.case_id == case_id,
        AgentGraphRun.status == "waiting_human",
    ).order_by(AgentGraphRun.created_at.desc()).with_for_update().first()
    if run is None:
        case_exists = db.query(CaseRecord.id).filter(CaseRecord.id == case_id).first()
        if case_exists is None:
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=409, detail="No waiting_human graph run to resume")

    tasks = db.query(AgentTask).filter(
        AgentTask.graph_run_id == run.id,
        AgentTask.status == "waiting_human",
    ).order_by(AgentTask.id.asc()).all()
    if not tasks:
        raise HTTPException(status_code=409, detail="No waiting_human task to resume")

    payload = dict(run.input_payload or {})
    payload["credential_id"] = credential_id
    run.input_payload = payload
    run.status = "queued"
    run.next_run_at = datetime.now(timezone.utc)
    run.lease_owner = None
    run.lease_expires_at = None
    for task in tasks:
        task.status = "ready"
        task.error_message = None
        task.finished_at = None

    case_timeline_service.append(
        db,
        case_id=case_id,
        graph_run_id=run.id,
        task_id=tasks[0].id,
        event_type="human_resume",
        title="Human input supplied: probe credential",
        actor_type="human",
        actor_id=str(principal.user_id),
        idempotency_key=f"human-resume:{run.id}:{credential_id}",
        payload={"task_ids": [item.id for item in tasks]},
    )
    security_audit_service.append(
        db,
        event_type="agent_graph.resume",
        outcome="success",
        actor_user_id=principal.user_id,
        actor_session_id=principal.session_id,
        target_type="agent_graph_run",
        target_id=run.id,
        details={"case_id": case_id, "task_ids": [item.id for item in tasks]},
    )
    db.commit()
    db.refresh(run)
    return CasePipelineResponse(**graph_service.view(run))


@router.get("/{case_id}/graph-runs")
async def list_case_graph_runs(case_id: int, db: Session = Depends(get_db)):
    rows = db.query(AgentGraphRun).filter(AgentGraphRun.case_id == case_id).order_by(AgentGraphRun.created_at.desc()).all()
    return {"case_id": case_id, "items": [_graph_view(item) for item in rows]}


@router.get("/{case_id}/graph-runs/{graph_run_id}")
async def get_case_graph_run(case_id: int, graph_run_id: str, db: Session = Depends(get_db)):
    run = db.query(AgentGraphRun).filter(AgentGraphRun.id == graph_run_id, AgentGraphRun.case_id == case_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Graph run not found")
    tasks = db.query(AgentTask).filter(AgentTask.graph_run_id == run.id).order_by(AgentTask.id.asc()).all()
    calls = db.query(AgentToolCall).filter(AgentToolCall.graph_run_id == run.id).order_by(AgentToolCall.id.asc()).all()
    checkpoint = db.query(AgentCheckpoint).filter(AgentCheckpoint.graph_run_id == run.id).order_by(AgentCheckpoint.id.desc()).first()
    return {
        **_graph_view(run),
        "tasks": [{
            "id": item.id, "task_code": item.task_code, "task_type": item.task_type, "graph_node": item.graph_node,
            "goal": item.goal, "assigned_agent_type": item.assigned_agent_type, "status": item.status,
            "priority": item.priority, "attempt_count": item.attempt_count, "max_attempts": item.max_attempts,
            "insight_round": item.insight_round, "output_payload": item.output_payload or {},
            "error_message": item.error_message, "started_at": item.started_at, "finished_at": item.finished_at,
        } for item in tasks],
        "tool_calls": [{
            "id": item.id, "task_id": item.task_id, "agent_run_id": item.agent_run_id, "tool_id": item.tool_id,
            "mode": item.mode, "status": item.status, "policy_decision": item.policy_decision or {},
            "result_payload": item.result_payload or {}, "error_message": item.error_message,
            "duration_ms": item.duration_ms, "started_at": item.started_at, "finished_at": item.finished_at,
        } for item in calls],
        "checkpoint": ({
            "id": checkpoint.id, "current_node": checkpoint.current_node, "state_payload": checkpoint.state_payload,
            "pending_tasks": checkpoint.pending_tasks, "budget_snapshot": checkpoint.budget_snapshot,
            "created_at": checkpoint.created_at,
        } if checkpoint else None),
    }


@router.get("/{case_id}/timeline")
async def get_case_timeline(case_id: int, limit: int = Query(500, ge=1, le=1000), db: Session = Depends(get_db)):
    rows = db.query(CaseTimelineEvent).filter(CaseTimelineEvent.case_id == case_id).order_by(CaseTimelineEvent.created_at.asc()).limit(limit).all()
    return {"case_id": case_id, "items": [{
        "id": item.id, "graph_run_id": item.graph_run_id, "task_id": item.task_id, "event_type": item.event_type,
        "title": item.title, "payload": item.payload or {}, "actor_type": item.actor_type, "actor_id": item.actor_id,
        "correlation_id": item.correlation_id, "created_at": item.created_at,
    } for item in rows]}


@router.get("/{case_id}/hypotheses")
async def get_case_hypotheses(case_id: int, db: Session = Depends(get_db)):
    rows = db.query(CaseHypothesis).filter(CaseHypothesis.case_id == case_id).order_by(CaseHypothesis.insight_round.desc(), CaseHypothesis.confidence.desc()).all()
    return {"case_id": case_id, "items": [{
        "id": item.id, "graph_run_id": item.graph_run_id, "task_id": item.task_id,
        "hypothesis_code": item.hypothesis_code, "cause_code": item.cause_code, "cause": item.cause,
        "confidence": item.confidence, "supporting_evidence_ids": item.supporting_evidence_ids or [],
        "contradicting_evidence_ids": item.contradicting_evidence_ids or [], "missing_evidence": item.missing_evidence or [],
        "next_probe_requests": item.next_probe_requests or [], "status": item.status, "insight_round": item.insight_round,
        "critic_decision": item.critic_decision, "critic_payload": item.critic_payload or {},
    } for item in rows]}


@router.get("/{case_id}/agent-budget")
async def get_case_agent_budget(case_id: int, graph_run_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(AgentBudget).filter(AgentBudget.case_id == case_id)
    if graph_run_id:
        query = query.filter(AgentBudget.graph_run_id == graph_run_id)
    item = query.order_by(AgentBudget.id.desc()).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Agent budget not found")
    return {
        "case_id": case_id, "graph_run_id": item.graph_run_id,
        "limits": {name: getattr(item, f"max_{name}") for name in ("agent_runs", "llm_calls", "tool_calls", "probe_calls", "replan_count", "runtime_seconds", "target_devices")},
        "usage": {
            "agent_runs": item.used_agent_runs, "llm_calls": item.used_llm_calls, "tool_calls": item.used_tool_calls,
            "probe_calls": item.used_probe_calls, "replan_count": item.used_replan_count,
            "runtime_seconds": item.used_runtime_seconds, "target_devices": len(item.target_device_ids or []),
        },
        "exhausted": item.exhausted, "exhausted_reason": item.exhausted_reason,
    }


@router.get("/{case_id}/agents")
async def list_case_agents(case_id: int, db: Session = Depends(get_db)):
    case = db.query(CaseRecord.id).filter(CaseRecord.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    runs = db.query(AgentRun).filter(AgentRun.case_id == case_id).order_by(AgentRun.started_at.asc()).all()
    claims = db.query(AgentClaim).filter(AgentClaim.case_id == case_id).order_by(AgentClaim.created_at.asc()).all()
    run_map = {item.id: item for item in runs}
    claim_groups = {}
    for claim in claims:
        claim_groups.setdefault(claim.agent_run_id, []).append(claim)

    return {
        "case_id": case_id,
        "runs": [
            {
                "id": run.id,
                "agent_type": run.agent_type.value if hasattr(run.agent_type, "value") else str(run.agent_type),
                "agent_name": run.agent_name,
                "status": run.status.value if hasattr(run.status, "value") else str(run.status),
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "duration_ms": run.duration_ms,
                "output_payload": run.output_payload or {},
                "claims": [
                    {
                        "id": claim.id,
                        "claim_type": claim.claim_type,
                        "claim_text": claim.claim_text,
                        "status": claim.status.value if hasattr(claim.status, "value") else str(claim.status),
                        "confidence": claim.confidence,
                        "evidence_refs": claim.evidence_refs or [],
                        "gaps": claim.gaps or [],
                    }
                    for claim in claim_groups.get(run.id, [])
                ],
            }
            for run in run_map.values()
        ],
    }


@router.get("/{case_id}/plans")
async def list_case_plans(case_id: int, db: Session = Depends(get_db)):
    case = db.query(CaseRecord.id).filter(CaseRecord.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    plans = db.query(RemediationPlan).filter(RemediationPlan.case_id == case_id).order_by(RemediationPlan.created_at.desc()).all()
    return {
        "case_id": case_id,
        "plans": [
            {
                "id": item.id,
                "plan_code": item.plan_code,
                "status": item.status.value if hasattr(item.status, "value") else str(item.status),
                "execution_mode": item.execution_mode,
                "approval_status": item.approval_status,
                "risk_level": item.risk_level,
                "summary": item.summary,
                "plan_payload": item.plan_payload or {},
                "rollback_payload": item.rollback_payload or {},
                "safety_checks": item.safety_checks or {},
                "created_at": item.created_at,
            }
            for item in plans
        ],
    }
