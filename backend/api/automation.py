"""
自动化中心API接口
提供自动化相关的REST API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from database import get_db
from models.agenticops import CaseRecord, ExecutionRun, MemoryEntry, MemoryType, RemediationPlan, RemediationPlanStatus
from models.automation import (
    Site, LogSample, LogAnalysisResult,
    AutomationApproval, AutomationPolicy, AutomationTask, AutomationTaskFeedback
)
from services.feedback_learning_service import feedback_learning_service
from services.ssh_service import ssh_service
from services.site_automation_service import site_automation_service
from services.log_sampler import log_sampler
from api.schemas.automation import (
    ApprovalDecisionRequest,
    ApprovalInitiateRequest,
    TaskFeedbackRequest,
    TriggerDiagnosisRequest,
    TaskFeedbackListResponse,
    FeedbackStatsResponse,
    FeedbackTrendsResponse,
    FeedbackInsightsResponse,
    ManualActionResponse
)

router = APIRouter(prefix="/api/automation", tags=["自动化中心"])


def _parse_optional_date(date_str: Optional[str], field_name: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format, use YYYY-MM-DD")


def _build_evidence_status(task: AutomationTask) -> Dict[str, Any]:
    """
    归一化任务证据状态，避免前端将任务pending误解为证据pending。
    """
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
        "message": inspection.get("error") or ""
    }


def _build_plan_evidence_status(plan: RemediationPlan, execution: Optional[ExecutionRun]) -> Dict[str, Any]:
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


def _map_plan_status(plan: RemediationPlan, execution: Optional[ExecutionRun]) -> str:
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


def _build_legacy_task_from_plan(plan: RemediationPlan) -> Dict[str, Any]:
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
        "status": _map_plan_status(plan, latest_execution),
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
        "evidence_status": _build_plan_evidence_status(plan, latest_execution),
        "recommended_action_type": (plan.plan_payload or {}).get("action_type"),
        "manual_intervention_required": plan.execution_mode != "auto" or plan.approval_status not in {"approved", "not_required"},
        "device_ip": case.device_ip if case else None,
        "case_id": plan.case_id,
        "case_code": case.case_code if case else None,
        "source_model": "remediation_plan",
        "approval_status": plan.approval_status,
        "risk_level": plan.risk_level,
    }


def _task_sort_key(item: Dict[str, Any]) -> float:
    created_at = item.get("created_at")
    if created_at is None:
        return 0.0
    try:
        return created_at.timestamp()
    except Exception:
        return 0.0


def _get_legacy_task_or_plan(db: Session, task_id: int) -> tuple[Optional[AutomationTask], Optional[RemediationPlan]]:
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if task is not None:
        return task, None
    plan = db.query(RemediationPlan).filter(RemediationPlan.id == task_id).first()
    return None, plan


def _list_plan_feedback_entries(db: Session, plan: RemediationPlan) -> List[MemoryEntry]:
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


def _append_legacy_approval(task: AutomationTask, *, stage: str, payload: Dict[str, Any]) -> None:
    trail = list(task.audit_trail or [])
    trail.append(
        {
            "stage": "Approval",
            "title": stage,
            "payload": payload,
        }
    )
    task.audit_trail = trail


def _get_legacy_pending_approvals_query(db: Session, site_id: Optional[int], approver: Optional[str]):
    query = db.query(AutomationTask).filter(AutomationTask.status == "waiting_approval")
    if site_id is not None:
        query = query.filter(AutomationTask.site_id == site_id)
    if approver:
        # Legacy model没有审批人分配字段，这里仅保留接口形态
        query = query
    return query


# ============ 基地管理 ============

@router.get("/sites")
async def get_sites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取所有基地列表"""
    sites = db.query(Site).offset(skip).limit(limit).all()
    enabled_map = site_automation_service.get_site_enabled_map(db)
    return {
        "total": db.query(Site).count(),
        "sites": [
            {
                "id": site.id,
                "site_code": site.site_code,
                "site_name": site.site_name,
                "description": site.description,
                "automation_enabled": enabled_map.get(site.id, False),
            }
            for site in sites
        ]
    }


@router.get("/sites/{site_id}")
async def get_site(site_id: int, db: Session = Depends(get_db)):
    """获取基地详情"""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    enabled_map = site_automation_service.get_site_enabled_map(db)
    return {
        "id": site.id,
        "site_code": site.site_code,
        "site_name": site.site_name,
        "description": site.description,
        "automation_enabled": enabled_map.get(site.id, False),
    }


@router.put("/sites/{site_id}/automation-toggle")
async def toggle_site_automation(
    site_id: int,
    enabled: bool,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    site_automation_service.set_site_enabled(db, site_id, enabled)

    async def _refresh_sampler_safely():
        try:
            from services.log_sampler import log_sampler
            await log_sampler.refresh_jobs()
        except Exception:
            # 开关结果应优先返回，采样器刷新失败仅记录日志
            import logging
            logging.getLogger(__name__).exception("Failed to refresh log sampler after site toggle")

    background_tasks.add_task(_refresh_sampler_safely)
    return {"site_id": site_id, "enabled": bool(enabled), "refresh_scheduled": True}


# ============ 日志采样 ============

@router.get("/samples")
async def get_log_samples(
    site_id: Optional[int] = None,
    is_abnormal: Optional[bool] = None,
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取日志采样列表"""
    query = db.query(LogSample)

    if site_id:
        query = query.filter(LogSample.site_id == site_id)
    if is_abnormal is not None:
        query = query.filter(LogSample.is_abnormal == is_abnormal)
    
    # 时间范围筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(LogSample.sampled_at >= start_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format, use YYYY-MM-DD")
    
    if end_date:
        try:
            # 结束日期包含当天，所以加一天
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(LogSample.sampled_at < end_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format, use YYYY-MM-DD")

    total = query.count()
    samples = query.order_by(LogSample.sampled_at.desc()).offset(skip).limit(limit).all()

    # 添加设备IP信息
    samples_with_device_ip = []
    for sample in samples:
        sample_dict = {
            "id": sample.id,
            "netbox_device_id": sample.netbox_device_id,
            "site_id": sample.site_id,
            "error_count": sample.error_count,
            "crc_error_count": sample.crc_error_count,
            "flap_count": sample.flap_count,
            "neighbor_change_count": sample.neighbor_change_count,
            "sampled_at": sample.sampled_at,
            "time_window_start": sample.time_window_start,
            "time_window_end": sample.time_window_end,
            "is_abnormal": sample.is_abnormal,
            "abnormal_type": None,
            "raw_data": sample.raw_data,
            "created_at": sample.created_at,
            "batch_id": sample.raw_data.get("batch_id") if isinstance(sample.raw_data, dict) else None,
            "signal_summary": sample.raw_data.get("signal_summary") if isinstance(sample.raw_data, dict) else None,
            "trigger_reason": sample.raw_data.get("trigger_reason") if isinstance(sample.raw_data, dict) else None,
            "case_id": ((sample.raw_data or {}).get("case") or {}).get("case_id") if isinstance(sample.raw_data, dict) else None,
            "case_code": ((sample.raw_data or {}).get("case") or {}).get("case_code") if isinstance(sample.raw_data, dict) else None,
        }
        if sample_dict["signal_summary"]:
            sample_dict["abnormal_type"] = sample_dict["signal_summary"].get("primary_signal")
        
        # 从raw_data中获取设备IP
        if sample.raw_data and "device_ip" in sample.raw_data:
            sample_dict["device_ip"] = sample.raw_data["device_ip"]
        
        samples_with_device_ip.append(sample_dict)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "returned": len(samples_with_device_ip),
        "has_more": skip + len(samples_with_device_ip) < total,
        "samples": samples_with_device_ip
    }


@router.get("/samples/{sample_id}")
async def get_log_sample(sample_id: int, db: Session = Depends(get_db)):
    """获取日志采样详情"""
    sample = db.query(LogSample).filter(LogSample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    return sample


# ============ 分析结果 ============

@router.get("/analysis-results")
async def get_analysis_results(
    site_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取分析结果列表"""
    query = db.query(LogAnalysisResult)

    if site_id:
        query = query.filter(LogAnalysisResult.site_id == site_id)
    if severity:
        query = query.filter(LogAnalysisResult.severity == severity)
    if status:
        query = query.filter(LogAnalysisResult.status == status)
    
    # 时间范围筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(LogAnalysisResult.created_at >= start_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format, use YYYY-MM-DD")
    
    if end_date:
        try:
            # 结束日期包含当天，所以加一天
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(LogAnalysisResult.created_at < end_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format, use YYYY-MM-DD")

    total = query.count()
    results = query.order_by(LogAnalysisResult.created_at.desc()).offset(skip).limit(limit).all()

    # 添加关联的采样数据中的设备IP
    results_with_device_ip = []
    for result in results:
        result_dict = {
            "id": result.id,
            "netbox_device_id": result.netbox_device_id,
            "site_id": result.site_id,
            "related_sample_id": result.related_sample_id,
            "analysis_type": result.analysis_type,
            "confidence": result.confidence,
            "summary": result.summary,
            "severity": result.severity,
            "recommendation": result.recommendation,
            "evidence": result.evidence,
            "status": result.status,
            "created_at": result.created_at,
            "updated_at": result.updated_at
        }
        
        # 从关联的采样数据中获取设备IP
        if result.related_sample_id:
            sample = db.query(LogSample).filter(LogSample.id == result.related_sample_id).first()
            if sample and sample.raw_data and "device_ip" in sample.raw_data:
                result_dict["device_ip"] = sample.raw_data["device_ip"]
        
        results_with_device_ip.append(result_dict)

    return {
        "total": total,
        "results": results_with_device_ip
    }


@router.get("/analysis-results/{result_id}")
async def get_analysis_result(result_id: int, db: Session = Depends(get_db)):
    """获取分析结果详情"""
    result = db.query(LogAnalysisResult).filter(LogAnalysisResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    return result


# ============ 自动化任务 ============

@router.get("/tasks")
async def get_automation_tasks(
    site_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取自动化任务列表"""
    legacy_query = db.query(AutomationTask)

    if site_id:
        legacy_query = legacy_query.filter(AutomationTask.site_id == site_id)
    if status:
        legacy_query = legacy_query.filter(AutomationTask.status == status)
    
    # 时间范围筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            legacy_query = legacy_query.filter(AutomationTask.created_at >= start_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format, use YYYY-MM-DD")
    
    if end_date:
        try:
            # 结束日期包含当天，所以加一天
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            legacy_query = legacy_query.filter(AutomationTask.created_at < end_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format, use YYYY-MM-DD")

    tasks = legacy_query.order_by(AutomationTask.created_at.desc()).all()

    # 添加设备IP信息
    tasks_with_device_ip = []
    for task in tasks:
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
                "created_at": latest_feedback.created_at
            } if latest_feedback else None
        }
        task_dict["evidence_status"] = _build_evidence_status(task)

        action_type = (task.decision_result or {}).get("context", {}).get("recommended_action_type")
        task_dict["recommended_action_type"] = action_type
        task_dict["manual_intervention_required"] = (
            action_type in {"replace_hardware", "manual_investigation"}
            or bool(task.need_human_confirm)
            or task.status in {"waiting_confirm", "waiting_approval"}
        )
        
        # 从context中获取设备IP
        if task.decision_result and "context" in task.decision_result:
            context = task.decision_result["context"]
            if "device_ip" in context:
                task_dict["device_ip"] = context["device_ip"]
        
        tasks_with_device_ip.append(task_dict)

    plan_query = db.query(RemediationPlan).join(CaseRecord, RemediationPlan.case_id == CaseRecord.id)
    if site_id:
        plan_query = plan_query.filter(CaseRecord.site_id == site_id)
    if start_date:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        plan_query = plan_query.filter(RemediationPlan.created_at >= start_datetime)
    if end_date:
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        plan_query = plan_query.filter(RemediationPlan.created_at < end_datetime)

    plan_items = [_build_legacy_task_from_plan(plan) for plan in plan_query.order_by(RemediationPlan.created_at.desc()).all()]
    if status:
        plan_items = [item for item in plan_items if item["status"] == status]

    combined_tasks = tasks_with_device_ip + plan_items
    combined_tasks.sort(key=_task_sort_key, reverse=True)
    total = len(combined_tasks)
    paged_tasks = combined_tasks[skip:skip + limit]

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "returned": len(paged_tasks),
        "has_more": skip + len(paged_tasks) < total,
        "tasks": paged_tasks
    }


@router.get("/tasks/{task_id}")
async def get_automation_task(task_id: int, db: Session = Depends(get_db)):
    """获取自动化任务详情"""
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if not task:
        plan = db.query(RemediationPlan).filter(RemediationPlan.id == task_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Task not found")
        task_dict = _build_legacy_task_from_plan(plan)
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

    # 转换为字典并添加设备IP
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
        "feedbacks": [
            {
                "id": feedback.id,
                "verdict": feedback.verdict,
                "comment": feedback.comment,
                "reviewer": feedback.reviewer,
                "tags": feedback.tags,
                "created_at": feedback.created_at
            }
            for feedback in feedbacks
        ]
    }
    task_dict["evidence_status"] = _build_evidence_status(task)

    action_type = (task.decision_result or {}).get("context", {}).get("recommended_action_type")
    task_dict["recommended_action_type"] = action_type
    task_dict["manual_intervention_required"] = (
        action_type in {"replace_hardware", "manual_investigation"}
        or bool(task.need_human_confirm)
        or task.status in {"waiting_confirm", "waiting_approval"}
    )
    
    # 从context中获取设备IP
    if task.decision_result and "context" in task.decision_result:
        context = task.decision_result["context"]
        if "device_ip" in context:
            task_dict["device_ip"] = context["device_ip"]
    
    return task_dict


@router.post("/tasks/{task_id}/approval/initiate")
async def initiate_task_approval(
    task_id: int,
    payload: ApprovalInitiateRequest,
    db: Session = Depends(get_db),
):
    task, plan = _get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if plan is not None:
        safety_checks = dict(plan.safety_checks or {})
        approval_history = list(safety_checks.get("approval_history") or [])
        approval_history.append(
            {
                "stage": "initiate",
                "risk_level": (payload.risk_level or "medium").lower(),
                "initiator": payload.initiator or "operator",
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
        raise HTTPException(status_code=400, detail=f"Task status {task.status} cannot initiate approval")

    task.status = "waiting_approval"
    task.need_human_confirm = True
    task.updated_at = datetime.now()
    _append_legacy_approval(
        task,
        stage="发起审批",
        payload={
            "initiator": payload.initiator or "operator",
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


@router.post("/tasks/{task_id}/approval/decision")
async def decide_task_approval(
    task_id: int,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
):
    task, plan = _get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if plan is not None:
        decision = (payload.decision or "").lower()
        if decision not in {"approved", "rejected"}:
            raise HTTPException(status_code=400, detail="decision must be approved|rejected")

        safety_checks = dict(plan.safety_checks or {})
        approval_history = list(safety_checks.get("approval_history") or [])
        approval_history.append(
            {
                "stage": "decision",
                "decision": decision,
                "approver": payload.approver,
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

    decision = (payload.decision or "").lower()
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be approved|rejected")

    duplicate = db.query(AutomationApproval).filter(
        AutomationApproval.task_id == task_id,
        AutomationApproval.approver == payload.approver,
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="approver has already submitted a decision")

    approval = AutomationApproval(
        task_id=task_id,
        approver=payload.approver,
        decision=decision,
        comment=payload.comment,
        decided_at=datetime.now(),
    )
    db.add(approval)

    task.status = "pending" if decision == "approved" else "aborted"
    task.updated_at = datetime.now()
    _append_legacy_approval(
        task,
        stage="审批决策",
        payload={
            "approver": payload.approver,
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


@router.get("/tasks/{task_id}/approval/history")
async def get_task_approval_history(task_id: int, db: Session = Depends(get_db)):
    task, plan = _get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise HTTPException(status_code=404, detail="Task not found")

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


@router.get("/approvals/pending")
async def get_pending_approvals(
    site_id: Optional[int] = None,
    approver: Optional[str] = None,
    db: Session = Depends(get_db),
):
    items: List[Dict[str, Any]] = []

    legacy_tasks = _get_legacy_pending_approvals_query(db, site_id=site_id, approver=approver).order_by(
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


@router.get("/tasks/{task_id}/feedback", response_model=TaskFeedbackListResponse)
async def get_task_feedback(task_id: int, db: Session = Depends(get_db)):
    """获取任务反馈列表"""
    task, plan = _get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if plan is not None:
        feedbacks = _list_plan_feedback_entries(db, plan)
        return {
            "task_id": task_id,
            "total": len(feedbacks),
            "feedbacks": [
                {
                    "id": int(feedback.id),
                    "verdict": (feedback.content or {}).get("verdict"),
                    "comment": (feedback.content or {}).get("comment"),
                    "reviewer": (feedback.content or {}).get("reviewer"),
                    "tags": feedback.tags or [],
                    "created_at": feedback.created_at,
                }
                for feedback in feedbacks
            ],
        }

    feedbacks = db.query(AutomationTaskFeedback).filter(
        AutomationTaskFeedback.task_id == task_id
    ).order_by(AutomationTaskFeedback.created_at.desc()).all()

    return {
        "task_id": task_id,
        "total": len(feedbacks),
        "feedbacks": [
            {
                "id": feedback.id,
                "verdict": feedback.verdict,
                "comment": feedback.comment,
                "reviewer": feedback.reviewer,
                "tags": feedback.tags,
                "created_at": feedback.created_at
            }
            for feedback in feedbacks
        ]
    }


@router.post("/tasks/{task_id}/feedback")
async def submit_task_feedback(
    task_id: int,
    payload: TaskFeedbackRequest,
    db: Session = Depends(get_db)
):
    """提交任务人工反馈，用于研判闭环"""
    task, plan = _get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise HTTPException(status_code=404, detail="Task not found")

    allowed_verdicts = {"correct", "incorrect", "partial"}
    if payload.verdict not in allowed_verdicts:
        raise HTTPException(status_code=400, detail="verdict must be one of correct|incorrect|partial")

    if plan is not None:
        entry = MemoryEntry(
            case_id=plan.case_id,
            memory_type=MemoryType.FEEDBACK,
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
                "reviewer": payload.reviewer or "operator",
                "tags": payload.tags or [],
            },
        )
        db.add(entry)
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
                "reviewer": payload.reviewer or "operator",
                "tags": payload.tags or [],
                "created_at": entry.created_at,
            },
        }

    feedback = AutomationTaskFeedback(
        task_id=task_id,
        verdict=payload.verdict,
        comment=payload.comment,
        reviewer=payload.reviewer or "operator",
        tags=payload.tags or []
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
            "created_at": feedback.created_at
        }
    }


@router.get("/feedback/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    diagnosis_type: Optional[str] = None,
    site_id: Optional[int] = None,
    window_days: int = Query(30, ge=1, le=365),
    min_samples: int = Query(5, ge=1, le=200),
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """获取反馈统计（按诊断类型聚合）"""
    start_datetime = _parse_optional_date(start_date, "start_date")
    end_datetime = _parse_optional_date(end_date, "end_date")
    if end_datetime:
        end_datetime = end_datetime + timedelta(days=1)

    stats = feedback_learning_service.get_feedback_stats(
        db=db,
        diagnosis_type=diagnosis_type,
        site_id=site_id,
        window_days=window_days,
        min_samples=min_samples,
        start_date=start_datetime,
        end_date=end_datetime
    )
    return {
        "total_types": len(stats),
        "stats": stats
    }


@router.get("/feedback/trends", response_model=FeedbackTrendsResponse)
async def get_feedback_trends(
    diagnosis_type: Optional[str] = None,
    site_id: Optional[int] = None,
    window_days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """获取反馈趋势（按诊断类型/日期）"""
    start_datetime = _parse_optional_date(start_date, "start_date")
    end_datetime = _parse_optional_date(end_date, "end_date")
    if end_datetime:
        end_datetime = end_datetime + timedelta(days=1)

    return feedback_learning_service.get_feedback_trends(
        db=db,
        site_id=site_id,
        diagnosis_type=diagnosis_type,
        window_days=window_days,
        start_date=start_datetime,
        end_date=end_datetime
    )


@router.get("/feedback/insights", response_model=FeedbackInsightsResponse)
async def get_feedback_insights(
    site_id: Optional[int] = None,
    window_days: int = Query(30, ge=1, le=365),
    min_samples: int = Query(5, ge=1, le=200),
    top_n: int = Query(5, ge=1, le=20),
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """获取误判TopN与阈值调整建议"""
    start_datetime = _parse_optional_date(start_date, "start_date")
    end_datetime = _parse_optional_date(end_date, "end_date")
    if end_datetime:
        end_datetime = end_datetime + timedelta(days=1)

    return feedback_learning_service.get_feedback_insights(
        db=db,
        site_id=site_id,
        window_days=window_days,
        min_samples=min_samples,
        start_date=start_datetime,
        end_date=end_datetime,
        top_n=top_n
    )


# ============ 策略管理 ============

@router.get("/policies")
async def get_automation_policies(
    site_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取自动化策略列表"""
    query = db.query(AutomationPolicy)

    if site_id:
        query = query.filter(AutomationPolicy.site_id == site_id)
    if enabled is not None:
        query = query.filter(AutomationPolicy.enabled == enabled)

    total = query.count()
    policies = query.order_by(AutomationPolicy.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "policies": policies
    }


@router.get("/policies/{policy_id}")
async def get_automation_policy(policy_id: int, db: Session = Depends(get_db)):
    """获取自动化策略详情"""
    policy = db.query(AutomationPolicy).filter(AutomationPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


# ============ Dashboard统计 ============

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    site_id: Optional[int] = None,
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """获取Dashboard统计摘要"""
    # 基地数量
    sites_count = db.query(Site).count()

    # 采样统计
    samples_query = db.query(LogSample)
    if site_id:
        samples_query = samples_query.filter(LogSample.site_id == site_id)
    
    # 时间范围筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            samples_query = samples_query.filter(LogSample.sampled_at >= start_datetime)
        except ValueError:
            pass  # 如果日期格式错误，忽略时间筛选
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            samples_query = samples_query.filter(LogSample.sampled_at < end_datetime)
        except ValueError:
            pass  # 如果日期格式错误，忽略时间筛选
    
    samples_count = samples_query.count()
    abnormal_samples_count = samples_query.filter(LogSample.is_abnormal == True).count()

    # 分析结果统计
    analysis_query = db.query(LogAnalysisResult)
    if site_id:
        analysis_query = analysis_query.filter(LogAnalysisResult.site_id == site_id)
    
    # 时间范围筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            analysis_query = analysis_query.filter(LogAnalysisResult.created_at >= start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            analysis_query = analysis_query.filter(LogAnalysisResult.created_at < end_datetime)
        except ValueError:
            pass
    
    analysis_count = analysis_query.count()
    critical_count = analysis_query.filter(LogAnalysisResult.severity == "critical").count()
    warning_count = analysis_query.filter(LogAnalysisResult.severity == "warning").count()

    # 任务统计
    tasks_query = db.query(AutomationTask)
    if site_id:
        tasks_query = tasks_query.filter(AutomationTask.site_id == site_id)
    
    # 时间范围筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            tasks_query = tasks_query.filter(AutomationTask.created_at >= start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            tasks_query = tasks_query.filter(AutomationTask.created_at < end_datetime)
        except ValueError:
            pass
    
    tasks_count = tasks_query.count()
    running_tasks_count = tasks_query.filter(AutomationTask.status == "running").count()
    success_tasks_count = tasks_query.filter(AutomationTask.status == "success").count()
    failed_tasks_count = tasks_query.filter(AutomationTask.status == "failed").count()

    plan_query = db.query(RemediationPlan).join(CaseRecord, RemediationPlan.case_id == CaseRecord.id)
    if site_id:
        plan_query = plan_query.filter(CaseRecord.site_id == site_id)
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            plan_query = plan_query.filter(RemediationPlan.created_at >= start_datetime)
        except ValueError:
            pass
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            plan_query = plan_query.filter(RemediationPlan.created_at < end_datetime)
        except ValueError:
            pass

    tasks_count += plan_query.count()
    running_tasks_count += plan_query.filter(RemediationPlan.status == RemediationPlanStatus.EXECUTING).count()
    success_tasks_count += plan_query.filter(RemediationPlan.status == RemediationPlanStatus.SUCCEEDED).count()
    failed_tasks_count += plan_query.filter(RemediationPlan.status == RemediationPlanStatus.FAILED).count()

    try:
        feedback_stats = feedback_learning_service.get_feedback_stats(
            db=db,
            site_id=site_id
        )
    except Exception:
        feedback_stats = {}
    feedback_total = sum(item.get("total", 0) for item in feedback_stats.values())
    feedback_correct = sum(item.get("correct", 0) for item in feedback_stats.values())
    feedback_incorrect = sum(item.get("incorrect", 0) for item in feedback_stats.values())
    feedback_partial = sum(item.get("partial", 0) for item in feedback_stats.values())

    return {
        "sites": {
            "total": sites_count
        },
        "samples": {
            "total": samples_count,
            "abnormal": abnormal_samples_count,
            "abnormal_rate": round(abnormal_samples_count / samples_count * 100, 2) if samples_count > 0 else 0
        },
        "analysis": {
            "total": analysis_count,
            "critical": critical_count,
            "warning": warning_count,
            "info": analysis_count - critical_count - warning_count
        },
        "tasks": {
            "total": tasks_count,
            "running": running_tasks_count,
            "success": success_tasks_count,
            "failed": failed_tasks_count,
            "success_rate": round(success_tasks_count / tasks_count * 100, 2) if tasks_count > 0 else 0
        },
        "feedback": {
            "total": feedback_total,
            "correct": feedback_correct,
            "incorrect": feedback_incorrect,
            "partial": feedback_partial,
            "correct_rate": round(feedback_correct / feedback_total * 100, 2) if feedback_total > 0 else 0,
            "incorrect_rate": round(feedback_incorrect / feedback_total * 100, 2) if feedback_total > 0 else 0
        }
    }


@router.get("/dashboard/hourly-trends")
async def get_dashboard_hourly_trends(
    site_id: Optional[int] = None,
    date: Optional[str] = Query(None, description="日期，格式：YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """获取Dashboard 24小时趋势数据"""
    # 如果没有指定日期，使用今天
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # 计算时间范围（整天）
    start_datetime = target_date
    end_datetime = target_date + timedelta(days=1)
    
    # 查询指定日期的采样数据
    samples_query = db.query(LogSample).filter(
        LogSample.sampled_at >= start_datetime,
        LogSample.sampled_at < end_datetime
    )
    
    if site_id:
        samples_query = samples_query.filter(LogSample.site_id == site_id)
    
    samples = samples_query.order_by(LogSample.sampled_at).all()
    
    # 按小时分组统计
    hourly_data = {}
    for i in range(24):
        hourly_data[i] = {
            "hour": f"{i:02d}:00",
            "samples": 0,
            "abnormal": 0
        }
    
    for sample in samples:
        hour = sample.sampled_at.hour
        hourly_data[hour]["samples"] += 1
        if sample.is_abnormal:
            hourly_data[hour]["abnormal"] += 1
    
    # 转换为列表
    trends = list(hourly_data.values())
    
    return {
        "date": date,
        "trends": trends
    }


@router.get("/dashboard/trends")
async def get_dashboard_trends(
    site_id: Optional[int] = None,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """获取Dashboard趋势数据"""
    # 计算时间范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # 查询指定时间范围内的数据
    samples_query = db.query(LogSample).filter(
        LogSample.sampled_at >= start_date,
        LogSample.sampled_at <= end_date
    )
    if site_id:
        samples_query = samples_query.filter(LogSample.site_id == site_id)

    # 按天分组统计
    daily_stats = []
    for i in range(days):
        day_start = start_date + timedelta(days=i)
        day_end = day_start + timedelta(days=1)

        day_samples = samples_query.filter(
            LogSample.sampled_at >= day_start,
            LogSample.sampled_at < day_end
        ).all()

        daily_stats.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "samples": len(day_samples),
            "abnormal": len([s for s in day_samples if s.is_abnormal])
        })

    return {
        "period": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "days": days
        },
        "trends": daily_stats
    }


# ============ 人机协同动作 ============

@router.post("/tasks/{task_id}/dispatch-config", response_model=ManualActionResponse)
async def dispatch_config_to_device(task_id: int, db: Session = Depends(get_db)):
    """一键下发配置（示例动作，按厂商下发查看命令前置验证）"""
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in {"waiting_confirm", "waiting_approval", "aborted", "cancelled"} or bool(task.need_human_confirm):
        raise HTTPException(
            status_code=400,
            detail="task is not eligible for dispatch pre-check, complete manual confirmation/approval first",
        )

    context = (task.decision_result or {}).get("context", {})
    device_id = context.get("netbox_device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="task has no netbox device")

    from models.automation import SSHCredentialDeviceBinding

    binding = db.query(SSHCredentialDeviceBinding).filter(
        SSHCredentialDeviceBinding.netbox_device_id == device_id
    ).order_by(SSHCredentialDeviceBinding.updated_at.desc()).first()
    if not binding:
        raise HTTPException(status_code=400, detail="no ssh credential binding found for this device")

    try:
        dry_run_result = ssh_service.execute_commands(
            db=db,
            credential_id=binding.credential_id,
            netbox_device_id=device_id,
            commands=["display current-configuration", "show running-config"],
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"dispatch pre-check failed: {exc}")

    trail = task.audit_trail or []
    trail.append(
        {
            "stage": "Inspection",
            "title": "人工触发一键下发前置检查",
            "payload": {
                "operator_action": "dispatch_config",
                "dry_run": dry_run_result,
            },
        }
    )
    task.audit_trail = trail
    db.commit()

    return {
        "success": True,
        "message": "已执行下发前置检查，后续可按变更流程执行正式配置下发",
        "data": dry_run_result,
    }


# ============ 手动触发 ============

@router.post("/trigger-diagnosis", response_model=ManualActionResponse)
async def trigger_diagnosis(
    payload: TriggerDiagnosisRequest,
    db: Session = Depends(get_db)
):
    """手动触发研判"""
    sample_id = payload.sample_id
    sample = db.query(LogSample).filter(LogSample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    try:
        result = await log_sampler.create_case_for_sample(sample_id, rerun_pipeline=True)
        return {
            "success": True,
            "message": f"Case pipeline triggered for sample {sample_id}",
            "data": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



