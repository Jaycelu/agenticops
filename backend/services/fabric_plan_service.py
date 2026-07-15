from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from api.schemas.automation import ApprovalDecisionRequest, ApprovalInitiateRequest, TaskFeedbackRequest
from models.agenticops import RemediationPlan
from approvals.service import approval_service
from auth.schemas import Principal
from services.memory_ingestion_service import memory_ingestion_service


def get_plan_or_raise(db: Session, plan_id: int) -> RemediationPlan:
    plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).first()
    if plan is None:
        raise LookupError("Plan not found")
    return plan


def initiate_plan_approval(
    db: Session,
    plan_id: int,
    payload: ApprovalInitiateRequest,
    *,
    principal: Principal,
) -> Dict[str, Any]:
    plan = get_plan_or_raise(db, plan_id)
    if (payload.risk_level or "").lower() != (plan.risk_level or "").lower():
        raise ValueError("request risk_level must match the frozen plan")
    version = approval_service.initiate(db, plan_id, principal)
    return {
        "success": True,
        "plan_id": int(plan.id),
        "message": "Approval initiated for remediation plan",
        "approval_status": plan.approval_status,
        "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        "data": {"version": version.version, "plan_hash": version.plan_hash, "expires_at": version.expires_at},
    }


def decide_plan_approval(
    db: Session,
    plan_id: int,
    payload: ApprovalDecisionRequest,
    *,
    principal: Principal,
) -> Dict[str, Any]:
    record = approval_service.decide(db, plan_id, payload.decision, payload.comment, principal)
    plan = get_plan_or_raise(db, plan_id)
    return {
        "success": True,
        "plan_id": int(plan.id),
        "message": "Approval decision recorded",
        "approval_status": plan.approval_status,
        "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        "data": {"decision_id": int(record.id), "decided_plan_hash": record.decided_plan_hash},
    }


def get_plan_approval_history(db: Session, plan_id: int) -> Dict[str, Any]:
    plan = get_plan_or_raise(db, plan_id)
    history = approval_service.history(db, plan_id)
    return {"plan_id": int(plan.id), "total": len(history), "approvals": history}


def submit_plan_feedback(
    db: Session,
    plan_id: int,
    payload: TaskFeedbackRequest,
    *,
    reviewer: str,
) -> Dict[str, Any]:
    plan = get_plan_or_raise(db, plan_id)
    allowed_verdicts = {"correct", "incorrect", "partial"}
    if payload.verdict not in allowed_verdicts:
        raise ValueError("verdict must be one of correct|incorrect|partial")

    entry, _ = memory_ingestion_service.remember_feedback(
        db,
        case_id=plan.case_id,
        memory_key=f"plan-feedback:{plan.id}:{int(datetime.now().timestamp() * 1000)}",
        title=f"Plan Feedback {plan.plan_code}",
        summary=payload.comment or plan.summary or "",
        source="fabric_feedback",
        tags=payload.tags or [],
        confidence=0.75 if payload.verdict == "correct" else 0.45,
        success_score=1.0 if payload.verdict == "correct" else 0.3,
        content={
            "plan_id": int(plan.id),
            "plan_code": plan.plan_code,
            "case_id": int(plan.case_id),
            "verdict": payload.verdict,
            "comment": payload.comment,
            "reviewer": reviewer,
            "tags": payload.tags or [],
        },
    )
    db.commit()
    db.refresh(entry)
    return {
        "success": True,
        "message": "Feedback submitted",
        "feedback": {
            "id": int(entry.id),
            "plan_id": int(plan.id),
            "verdict": payload.verdict,
            "comment": payload.comment,
            "reviewer": reviewer,
            "tags": payload.tags or [],
            "created_at": entry.created_at,
        },
    }
