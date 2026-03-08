from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.agenticops import CaseRecord, ExecutionRun, MemoryEntry, MemoryType, RemediationPlan, RemediationPlanStatus
from models.automation import AutomationTask, AutomationTaskFeedback


def parse_optional_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d")


def build_plan_evidence_status(plan: RemediationPlan, execution: Optional[ExecutionRun]) -> Dict[str, Any]:
    if execution and str(execution.status) in {"ExecutionRunStatus.FAILED", "failed"}:
        return {
            "status": "failed",
            "topology_status": "success",
            "inspection_status": "completed",
            "final_status": "failed",
            "confidence": None,
            "message": execution.error_message or "",
        }
    if execution and str(execution.status) in {"ExecutionRunStatus.SUCCEEDED", "succeeded", "verified", "ExecutionRunStatus.VERIFIED"}:
        return {
            "status": "success",
            "topology_status": "success",
            "inspection_status": "completed",
            "final_status": "success",
            "confidence": None,
            "message": "",
        }
    if str(plan.status) in {"RemediationPlanStatus.EXECUTING", "executing"}:
        return {
            "status": "partial",
            "topology_status": "success",
            "inspection_status": "completed",
            "final_status": "running",
            "confidence": None,
            "message": "",
        }
    return {
        "status": "skipped",
        "topology_status": "success" if plan.case else "skipped",
        "inspection_status": "completed" if plan.plan_payload else "skipped",
        "final_status": "draft",
        "confidence": None,
        "message": "",
    }


def map_plan_status(plan: RemediationPlan, execution: Optional[ExecutionRun]) -> str:
    if execution:
        execution_status = execution.status.value if hasattr(execution.status, "value") else str(execution.status)
        status_map = {
            "pending": "pending",
            "running": "running",
            "succeeded": "success",
            "failed": "failed",
            "verifying": "running",
            "verified": "success",
            "rolled_back": "aborted",
        }
        return status_map.get(execution_status, execution_status)

    plan_status = plan.status.value if hasattr(plan.status, "value") else str(plan.status)
    status_map = {
        "draft": "pending",
        "pending_approval": "waiting_approval",
        "approved": "pending" if plan.execution_mode == "auto" else "waiting_confirm",
        "executing": "running",
        "succeeded": "success",
        "failed": "failed",
        "rolled_back": "aborted",
        "cancelled": "cancelled",
    }
    return status_map.get(plan_status, plan_status)


def build_evidence_status(task: AutomationTask) -> Dict[str, Any]:
    context = (task.decision_result or {}).get("context", {})
    context_aware = context.get("context_aware") or {}
    inspection = context_aware.get("inspection") or {}
    topology_context = context_aware.get("topology_context") or {}
    final_result = context_aware.get("final") or {}

    has_topology = bool((topology_context.get("device") or {}) or (topology_context.get("links") or []))
    inspection_status = inspection.get("status") or "skipped"
    final_confidence = final_result.get("confidence")

    if inspection_status == "success" and has_topology:
        status = "success"
    elif inspection_status in {"failed"}:
        status = "failed"
    elif inspection_status in {"manual_required"}:
        status = "manual_required"
    elif has_topology:
        status = "partial"
    else:
        status = "skipped"

    return {
        "status": status,
        "topology_status": "success" if has_topology else "skipped",
        "inspection_status": inspection_status,
        "final_status": "success" if final_result else "skipped",
        "confidence": final_confidence,
        "message": inspection.get("error") or "",
    }


def build_legacy_task_from_plan(plan: RemediationPlan) -> Dict[str, Any]:
    latest_execution = None
    if plan.execution_runs:
        latest_execution = sorted(
            plan.execution_runs,
            key=lambda item: item.started_at or item.created_at,
            reverse=True,
        )[0]

    case = plan.case
    context = {
        "case_id": plan.case_id,
        "case_code": case.case_code if case else None,
        "device_ip": case.device_ip if case else None,
        "netbox_device_id": case.netbox_device_id if case else None,
        "recommended_action_type": (plan.plan_payload or {}).get("action_type"),
    }

    return {
        "id": int(plan.id),
        "task_code": plan.plan_code,
        "policy_id": None,
        "site_id": case.site_id if case else None,
        "netbox_device_id": case.netbox_device_id if case else None,
        "status": map_plan_status(plan, latest_execution),
        "triggered_by": "agentic_case",
        "trigger_event": {
            "source": "remediation_plan",
            "case_id": plan.case_id,
            "execution_mode": plan.execution_mode,
            "approval_status": plan.approval_status,
        },
        "decision_result": {
            "summary": plan.summary,
            "context": context,
            "recommended_action_type": (plan.plan_payload or {}).get("action_type"),
            "plan_payload": plan.plan_payload or {},
            "rollback_payload": plan.rollback_payload or {},
            "safety_checks": plan.safety_checks or {},
        },
        "execution_result": (latest_execution.result_payload if latest_execution else {}),
        "audit_trail": (latest_execution.audit_trail if latest_execution else []),
        "need_human_confirm": plan.approval_status not in {"approved", "not_required"},
        "started_at": latest_execution.started_at if latest_execution else None,
        "finished_at": latest_execution.finished_at if latest_execution else None,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "latest_feedback": None,
        "evidence_status": build_plan_evidence_status(plan, latest_execution),
        "recommended_action_type": (plan.plan_payload or {}).get("action_type"),
        "manual_intervention_required": plan.execution_mode != "auto" or plan.approval_status not in {"approved", "not_required"},
        "device_ip": case.device_ip if case else None,
        "case_id": plan.case_id,
        "case_code": case.case_code if case else None,
        "source_model": "remediation_plan",
        "approval_status": plan.approval_status,
        "risk_level": plan.risk_level,
    }


def task_sort_key(item: Dict[str, Any]) -> float:
    created_at = item.get("created_at")
    if created_at is None:
        return 0.0
    try:
        return created_at.timestamp()
    except Exception:
        return 0.0


def get_legacy_task_or_plan(db: Session, task_id: int) -> tuple[Optional[AutomationTask], Optional[RemediationPlan]]:
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if task is not None:
        return task, None
    plan = db.query(RemediationPlan).filter(RemediationPlan.id == task_id).first()
    return None, plan


def list_plan_feedback_entries(db: Session, plan: RemediationPlan) -> List[MemoryEntry]:
    rows = (
        db.query(MemoryEntry)
        .filter(
            MemoryEntry.case_id == plan.case_id,
            MemoryEntry.memory_type == MemoryType.FEEDBACK,
        )
        .order_by(MemoryEntry.created_at.desc())
        .all()
    )
    return [
        item for item in rows
        if isinstance(item.content, dict) and item.content.get("plan_id") == int(plan.id)
    ]


def get_legacy_pending_approvals_query(db: Session, site_id: Optional[int], approver: Optional[str]):
    query = db.query(AutomationTask).filter(AutomationTask.status == "waiting_approval")
    if site_id is not None:
        query = query.filter(AutomationTask.site_id == site_id)
    if approver:
        query = query
    return query


def build_legacy_task_dict(db: Session, task: AutomationTask) -> Dict[str, Any]:
    try:
        latest_feedback = db.query(AutomationTaskFeedback).filter(
            AutomationTaskFeedback.task_id == task.id
        ).order_by(AutomationTaskFeedback.created_at.desc()).first()
    except Exception:
        latest_feedback = None

    task_dict = {
        "id": task.id,
        "task_code": task.task_code,
        "policy_id": task.policy_id,
        "site_id": task.site_id,
        "netbox_device_id": task.netbox_device_id,
        "status": task.status,
        "triggered_by": task.triggered_by,
        "trigger_event": task.trigger_event,
        "decision_result": task.decision_result,
        "execution_result": task.execution_result,
        "audit_trail": task.audit_trail or [],
        "need_human_confirm": task.need_human_confirm,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "latest_feedback": {
            "id": latest_feedback.id,
            "verdict": latest_feedback.verdict,
            "comment": latest_feedback.comment,
            "reviewer": latest_feedback.reviewer,
            "created_at": latest_feedback.created_at,
        } if latest_feedback else None,
        "source_model": "automation_task",
    }
    task_dict["evidence_status"] = build_evidence_status(task)
    action_type = (task.decision_result or {}).get("context", {}).get("recommended_action_type")
    task_dict["recommended_action_type"] = action_type
    task_dict["manual_intervention_required"] = (
        action_type in {"replace_hardware", "manual_investigation"}
        or bool(task.need_human_confirm)
        or task.status in {"waiting_confirm", "waiting_approval"}
    )
    if task.decision_result and "context" in task.decision_result:
        context = task.decision_result["context"]
        if "device_ip" in context:
            task_dict["device_ip"] = context["device_ip"]
    return task_dict


def list_compat_tasks(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    legacy_query = db.query(AutomationTask)
    if site_id:
        legacy_query = legacy_query.filter(AutomationTask.site_id == site_id)
    if status:
        legacy_query = legacy_query.filter(AutomationTask.status == status)

    if start_date:
        start_datetime = parse_optional_date(start_date)
        legacy_query = legacy_query.filter(AutomationTask.created_at >= start_datetime)
    if end_date:
        end_datetime = parse_optional_date(end_date) + timedelta(days=1)
        legacy_query = legacy_query.filter(AutomationTask.created_at < end_datetime)

    tasks_with_device_ip = [build_legacy_task_dict(db, task) for task in legacy_query.order_by(AutomationTask.created_at.desc()).all()]

    plan_query = db.query(RemediationPlan).join(CaseRecord, RemediationPlan.case_id == CaseRecord.id)
    if site_id:
        plan_query = plan_query.filter(CaseRecord.site_id == site_id)
    if start_date:
        plan_query = plan_query.filter(RemediationPlan.created_at >= parse_optional_date(start_date))
    if end_date:
        plan_query = plan_query.filter(RemediationPlan.created_at < parse_optional_date(end_date) + timedelta(days=1))

    plan_items = [build_legacy_task_from_plan(plan) for plan in plan_query.order_by(RemediationPlan.created_at.desc()).all()]
    if status:
        plan_items = [item for item in plan_items if item["status"] == status]

    combined_tasks = tasks_with_device_ip + plan_items
    combined_tasks.sort(key=task_sort_key, reverse=True)
    total = len(combined_tasks)
    paged_tasks = combined_tasks[skip:skip + limit]
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "returned": len(paged_tasks),
        "has_more": skip + len(paged_tasks) < total,
        "tasks": paged_tasks,
    }


def get_compat_task_detail(db: Session, task_id: int) -> Dict[str, Any]:
    task, plan = get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise LookupError("Task not found")

    if plan is not None:
        task_dict = build_legacy_task_from_plan(plan)
        task_dict["feedbacks"] = []
        task_dict["execution_history"] = [
            {
                "id": execution.id,
                "status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
                "executor_type": execution.executor_type,
                "executor_name": execution.executor_name,
                "started_at": execution.started_at,
                "finished_at": execution.finished_at,
                "error_message": execution.error_message,
            }
            for execution in sorted(plan.execution_runs, key=lambda item: item.started_at or item.created_at, reverse=True)
        ]
        return task_dict

    try:
        feedbacks = db.query(AutomationTaskFeedback).filter(
            AutomationTaskFeedback.task_id == task.id
        ).order_by(AutomationTaskFeedback.created_at.desc()).all()
    except Exception:
        feedbacks = []

    task_dict = build_legacy_task_dict(db, task)
    task_dict["feedbacks"] = [
        {
            "id": feedback.id,
            "verdict": feedback.verdict,
            "comment": feedback.comment,
            "reviewer": feedback.reviewer,
            "tags": feedback.tags,
            "created_at": feedback.created_at,
        }
        for feedback in feedbacks
    ]
    return task_dict


def list_pending_approval_items(
    db: Session,
    *,
    site_id: Optional[int] = None,
    approver: Optional[str] = None,
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []

    legacy_tasks = get_legacy_pending_approvals_query(db, site_id=site_id, approver=approver).order_by(
        AutomationTask.created_at.asc()
    ).limit(200).all()
    for task in legacy_tasks:
        items.append(
            {
                "task_id": task.id,
                "task_code": task.task_code,
                "site_id": task.site_id,
                "status": task.status,
                "source_model": "automation_task",
                "created_at": task.created_at,
            }
        )

    plan_query = db.query(RemediationPlan).join(CaseRecord, RemediationPlan.case_id == CaseRecord.id).filter(
        RemediationPlan.status == RemediationPlanStatus.PENDING_APPROVAL
    )
    if site_id is not None:
        plan_query = plan_query.filter(CaseRecord.site_id == site_id)
    plans = plan_query.order_by(RemediationPlan.created_at.asc()).limit(200).all()
    for plan in plans:
        items.append(
            {
                "task_id": int(plan.id),
                "task_code": plan.plan_code,
                "site_id": plan.case.site_id if plan.case else None,
                "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
                "source_model": "remediation_plan",
                "created_at": plan.created_at,
            }
        )

    items.sort(key=lambda item: item.get("created_at") or datetime.min)
    return {"total": len(items), "items": items}
