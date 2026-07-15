from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from api.schemas.automation import ApprovalDecisionRequest, ApprovalInitiateRequest, ManualActionResponse, TaskFeedbackRequest
from api.schemas.fabric import (
    ExecutionRunListResponse,
    ExecutionRunResponse,
    FabricOverviewResponse,
    RemediationPlanExecuteResponse,
    RemediationPlanListResponse,
    RemediationPlanResponse,
)
from models.agenticops import ExecutionRun, ExecutionRunStatus, RemediationPlan, RemediationPlanStatus
from services.post_execution_verification_service import post_execution_verification_service
from services.fabric_plan_service import (
    decide_plan_approval,
    get_plan_approval_history,
    initiate_plan_approval,
    submit_plan_feedback,
)
from services.execution_service import execution_service
from auth.dependencies import require_permissions
from auth.rbac import Permission
from auth.schemas import Principal

router = APIRouter(prefix="/api/fabric", tags=["Automation Fabric"])


@router.get("/overview", response_model=FabricOverviewResponse)
async def get_fabric_overview(db: Session = Depends(get_db)):
    total_plans = db.query(func.count(RemediationPlan.id)).scalar() or 0
    draft_plans = db.query(func.count(RemediationPlan.id)).filter(RemediationPlan.status == RemediationPlanStatus.DRAFT).scalar() or 0
    approved_plans = db.query(func.count(RemediationPlan.id)).filter(RemediationPlan.status == RemediationPlanStatus.APPROVED).scalar() or 0
    running_executions = db.query(func.count(ExecutionRun.id)).filter(ExecutionRun.status == ExecutionRunStatus.RUNNING).scalar() or 0
    failed_executions = db.query(func.count(ExecutionRun.id)).filter(ExecutionRun.status == ExecutionRunStatus.FAILED).scalar() or 0
    return FabricOverviewResponse(
        total_plans=total_plans,
        draft_plans=draft_plans,
        approved_plans=approved_plans,
        running_executions=running_executions,
        failed_executions=failed_executions,
    )


@router.get("/plans", response_model=RemediationPlanListResponse)
async def list_plans(
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(RemediationPlan)
    if case_id is not None:
        query = query.filter(RemediationPlan.case_id == case_id)
    if status:
        query = query.filter(RemediationPlan.status == status)

    total = query.count()
    items = query.order_by(RemediationPlan.created_at.desc()).offset(skip).limit(limit).all()
    return RemediationPlanListResponse(
        total=total,
        items=[
            RemediationPlanResponse(
                id=item.id,
                case_id=item.case_id,
                plan_code=item.plan_code,
                generated_by_agent_run_id=item.generated_by_agent_run_id,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                execution_mode=item.execution_mode,
                approval_status=item.approval_status,
                risk_level=item.risk_level,
                summary=item.summary,
                plan_payload=item.plan_payload or {},
                rollback_payload=item.rollback_payload or {},
                safety_checks=item.safety_checks or {},
                created_at=item.created_at,
                approved_at=item.approved_at,
            )
            for item in items
        ],
    )


@router.get("/plans/{plan_id}", response_model=RemediationPlanResponse)
async def get_plan(plan_id: int, db: Session = Depends(get_db)):
    item = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return RemediationPlanResponse(
        id=item.id,
        case_id=item.case_id,
        plan_code=item.plan_code,
        generated_by_agent_run_id=item.generated_by_agent_run_id,
        status=item.status.value if hasattr(item.status, "value") else str(item.status),
        execution_mode=item.execution_mode,
        approval_status=item.approval_status,
        risk_level=item.risk_level,
        summary=item.summary,
        plan_payload=item.plan_payload or {},
        rollback_payload=item.rollback_payload or {},
        safety_checks=item.safety_checks or {},
        created_at=item.created_at,
        approved_at=item.approved_at,
    )


@router.post("/plans/{plan_id}/approval/initiate", response_model=ManualActionResponse)
async def initiate_remediation_plan_approval(
    plan_id: int,
    payload: ApprovalInitiateRequest,
    principal: Principal = Depends(require_permissions(Permission.APPROVALS_REQUEST.value)),
    db: Session = Depends(get_db),
):
    try:
        return initiate_plan_approval(db, plan_id, payload, principal=principal)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/plans/{plan_id}/approval/decision", response_model=ManualActionResponse)
async def decide_remediation_plan_approval(
    plan_id: int,
    payload: ApprovalDecisionRequest,
    principal: Principal = Depends(require_permissions(Permission.APPROVALS_DECIDE.value)),
    db: Session = Depends(get_db),
):
    try:
        return decide_plan_approval(db, plan_id, payload, principal=principal)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/plans/{plan_id}/approval/history")
async def get_remediation_plan_approval_history(
    plan_id: int,
    db: Session = Depends(get_db),
):
    try:
        return get_plan_approval_history(db, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/plans/{plan_id}/feedback", response_model=ManualActionResponse)
async def submit_remediation_plan_feedback(
    plan_id: int,
    payload: TaskFeedbackRequest,
    principal: Principal = Depends(require_permissions(Permission.PROBES_RUN.value)),
    db: Session = Depends(get_db),
):
    try:
        return submit_plan_feedback(db, plan_id, payload, reviewer=principal.username)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/plans/{plan_id}/execute",
    response_model=RemediationPlanExecuteResponse,
)
async def execute_remediation_plan(
    plan_id: int,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=16, max_length=160),
    principal: Principal = Depends(require_permissions(Permission.EXECUTIONS_RUN.value)),
    db: Session = Depends(get_db),
):
    try:
        return await execution_service.execute_plan(
            db,
            plan_id,
            principal=principal,
            idempotency_key=idempotency_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/executions", response_model=ExecutionRunListResponse)
async def list_execution_runs(
    case_id: Optional[int] = None,
    remediation_plan_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(ExecutionRun)
    if case_id is not None:
        query = query.filter(ExecutionRun.case_id == case_id)
    if remediation_plan_id is not None:
        query = query.filter(ExecutionRun.remediation_plan_id == remediation_plan_id)
    if status:
        query = query.filter(ExecutionRun.status == status)

    total = query.count()
    items = query.order_by(ExecutionRun.started_at.desc()).offset(skip).limit(limit).all()
    return ExecutionRunListResponse(
        total=total,
        items=[
            ExecutionRunResponse(
                id=item.id,
                case_id=item.case_id,
                remediation_plan_id=item.remediation_plan_id,
                executor_type=item.executor_type,
                executor_name=item.executor_name,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                command_summary=item.command_summary,
                request_payload=item.request_payload or {},
                result_payload=item.result_payload or {},
                audit_trail=item.audit_trail or [],
                error_message=item.error_message,
                started_at=item.started_at,
                finished_at=item.finished_at,
                verified_at=item.verified_at,
            )
            for item in items
        ],
    )


@router.get("/executions/{execution_id}", response_model=ExecutionRunResponse)
async def get_execution_run(execution_id: int, db: Session = Depends(get_db)):
    item = db.query(ExecutionRun).filter(ExecutionRun.id == execution_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Execution run not found")
    return ExecutionRunResponse(
        id=item.id,
        case_id=item.case_id,
        remediation_plan_id=item.remediation_plan_id,
        executor_type=item.executor_type,
        executor_name=item.executor_name,
        status=item.status.value if hasattr(item.status, "value") else str(item.status),
        command_summary=item.command_summary,
        request_payload=item.request_payload or {},
        result_payload=item.result_payload or {},
        audit_trail=item.audit_trail or [],
        error_message=item.error_message,
        started_at=item.started_at,
        finished_at=item.finished_at,
        verified_at=item.verified_at,
    )


@router.post(
    "/executions/{execution_id}/verify-readonly",
    dependencies=[Depends(require_permissions(Permission.PROBES_RUN.value))],
)
async def verify_execution_readonly_harness(execution_id: int, db: Session = Depends(get_db)):
    """只读复查执行结果（Zabbix/ELK 快照），更新 execution / case 状态。"""
    result = await post_execution_verification_service.verify_execution_readonly(db, execution_id=execution_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message") or "verification_failed")
    return result
