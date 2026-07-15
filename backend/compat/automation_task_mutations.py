from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from api.schemas.automation import ApprovalDecisionRequest, ApprovalInitiateRequest, TaskFeedbackRequest
from compat.automation_task_views import get_legacy_task_or_plan
from models.agenticops import RemediationPlanStatus
from models.automation import AutomationApproval, AutomationTask, AutomationTaskFeedback
from services.memory_ingestion_service import memory_ingestion_service


def append_legacy_approval(task: AutomationTask, *, stage: str, payload: Dict[str, Any]) -> None:
    trail = list(task.audit_trail or [])
    trail.append(
        {
            "stage": "Approval",
            "title": stage,
            "payload": payload,
        }
    )
    task.audit_trail = trail


def initiate_task_approval_action(
    db: Session,
    task_id: int,
    payload: ApprovalInitiateRequest,
    *,
    initiator: str,
) -> Dict[str, Any]:
    task, plan = get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise LookupError("Task not found")

    if plan is not None:
        safety_checks = dict(plan.safety_checks or {})
        approval_history = list(safety_checks.get("approval_history") or [])
        approval_history.append(
            {
                "stage": "initiate",
                "risk_level": (payload.risk_level or "medium").lower(),
                "initiator": initiator,
                "created_at": datetime.now().isoformat(),
            }
        )
        safety_checks["approval_history"] = approval_history
        plan.safety_checks = safety_checks
        plan.approval_status = "pending"
        plan.status = RemediationPlanStatus.PENDING_APPROVAL
        db.commit()
        db.refresh(plan)
        return {
            "success": True,
            "task_id": task_id,
            "plan_id": int(plan.id),
            "message": "Approval initiated for remediation plan",
            "approval_status": plan.approval_status,
            "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        }

    if task.status not in {"waiting_confirm", "pending"}:
        raise ValueError(f"Task status {task.status} cannot initiate approval")

    task.status = "waiting_approval"
    task.need_human_confirm = True
    task.updated_at = datetime.now()
    append_legacy_approval(
        task,
        stage="发起审批",
        payload={
            "initiator": initiator,
            "risk_level": (payload.risk_level or "medium").lower(),
            "created_at": datetime.now().isoformat(),
        },
    )
    db.commit()
    db.refresh(task)
    return {
        "success": True,
        "task_id": task_id,
        "message": "Approval initiated for legacy automation task",
        "status": task.status,
    }


def decide_task_approval_action(
    db: Session,
    task_id: int,
    payload: ApprovalDecisionRequest,
    *,
    approver: str,
) -> Dict[str, Any]:
    task, plan = get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise LookupError("Task not found")

    decision = (payload.decision or "").lower()
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved|rejected")

    if plan is not None:
        safety_checks = dict(plan.safety_checks or {})
        approval_history = list(safety_checks.get("approval_history") or [])
        approval_history.append(
            {
                "stage": "decision",
                "decision": decision,
                "approver": approver,
                "comment": payload.comment,
                "created_at": datetime.now().isoformat(),
            }
        )
        safety_checks["approval_history"] = approval_history
        plan.safety_checks = safety_checks
        plan.approval_status = decision
        plan.approved_at = datetime.now() if decision == "approved" else None
        plan.status = RemediationPlanStatus.APPROVED if decision == "approved" else RemediationPlanStatus.REJECTED
        db.commit()
        db.refresh(plan)
        return {
            "success": True,
            "task_id": task_id,
            "plan_id": int(plan.id),
            "message": "Approval decision recorded for remediation plan",
            "approval_status": plan.approval_status,
            "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        }

    duplicate = db.query(AutomationApproval).filter(
        AutomationApproval.task_id == task_id,
        AutomationApproval.approver == approver,
    ).first()
    if duplicate:
        raise ValueError("approver has already submitted a decision")

    approval = AutomationApproval(
        task_id=task_id,
        approver=approver,
        decision=decision,
        comment=payload.comment,
        decided_at=datetime.now(),
    )
    db.add(approval)

    task.status = "pending" if decision == "approved" else "aborted"
    task.updated_at = datetime.now()
    append_legacy_approval(
        task,
        stage="审批决策",
        payload={
            "approver": approver,
            "decision": decision,
            "comment": payload.comment,
            "created_at": datetime.now().isoformat(),
        },
    )
    db.commit()
    db.refresh(task)
    db.refresh(approval)
    return {
        "success": True,
        "task_id": task_id,
        "message": "Approval decision recorded for legacy automation task",
        "approval": {
            "id": approval.id,
            "approver": approval.approver,
            "decision": approval.decision,
            "comment": approval.comment,
            "decided_at": approval.decided_at,
        },
        "status": task.status,
    }


def get_task_approval_history_view(db: Session, task_id: int) -> Dict[str, Any]:
    task, plan = get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise LookupError("Task not found")

    if plan is not None:
        history = list((plan.safety_checks or {}).get("approval_history") or [])
        return {"task_id": task_id, "total": len(history), "approvals": history}

    history_rows = db.query(AutomationApproval).filter(
        AutomationApproval.task_id == task_id
    ).order_by(AutomationApproval.created_at.asc()).all()
    history = [
        {
            "id": item.id,
            "approver": item.approver,
            "decision": item.decision,
            "comment": item.comment,
            "created_at": item.created_at,
            "decided_at": item.decided_at,
        }
        for item in history_rows
    ]
    return {"task_id": task_id, "total": len(history), "approvals": history}


def submit_task_feedback_action(
    db: Session,
    task_id: int,
    payload: TaskFeedbackRequest,
    *,
    reviewer: str,
) -> Dict[str, Any]:
    task, plan = get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise LookupError("Task not found")

    allowed_verdicts = {"correct", "incorrect", "partial"}
    if payload.verdict not in allowed_verdicts:
        raise ValueError("verdict must be one of correct|incorrect|partial")

    if plan is not None:
        entry, _ = memory_ingestion_service.remember_feedback(
            db,
            case_id=plan.case_id,
            memory_key=f"plan-feedback:{plan.id}:{int(datetime.now().timestamp() * 1000)}",
            title=f"Plan Feedback {plan.plan_code}",
            summary=payload.comment or plan.summary or "",
            source="automation_feedback",
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
                "task_id": task_id,
                "verdict": payload.verdict,
                "comment": payload.comment,
                "reviewer": reviewer,
                "tags": payload.tags or [],
                "created_at": entry.created_at,
            },
        }

    feedback = AutomationTaskFeedback(
        task_id=task_id,
        verdict=payload.verdict,
        comment=payload.comment,
        reviewer=reviewer,
        tags=payload.tags or [],
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {
        "success": True,
        "message": "Feedback submitted",
        "feedback": {
            "id": feedback.id,
            "task_id": feedback.task_id,
            "verdict": feedback.verdict,
            "comment": feedback.comment,
            "reviewer": feedback.reviewer,
            "tags": feedback.tags,
            "created_at": feedback.created_at,
        },
    }
