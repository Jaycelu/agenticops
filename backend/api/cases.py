from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

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
        CaseStatus.OPEN,
        CaseStatus.TRIAGED,
        CaseStatus.INVESTIGATING,
        CaseStatus.PLANNED,
        CaseStatus.EXECUTING,
        CaseStatus.VERIFYING,
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


@router.post("", response_model=CaseDetailResponse)
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


@router.post("/intake", response_model=CasePipelineResponse)
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


@router.post("/{case_id}/run-agents", response_model=CasePipelineResponse)
async def run_case_agents(
    case_id: int,
    base_name: Optional[str] = None,
    log_query: Optional[str] = None,
    time_range: str = "-15m,now",
    log_limit: int = Query(200, ge=1, le=1000),
    credential_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    result = await case_orchestrator.run_case_pipeline(
        db,
        case_id=case_id,
        base_name=base_name,
        log_query=log_query,
        time_range=time_range,
        log_limit=log_limit,
        credential_id=credential_id,
    )
    return CasePipelineResponse(**result)


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
