"""
自动化中心API接口
提供自动化相关的REST API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from database import get_db
from models.automation import (
    Site, LogSample, LogAnalysisResult,
    AutomationPolicy, AutomationTask, AutomationTaskFeedback
)
from services.automation_orchestrator import automation_orchestrator
from services.alert_service import alert_service
from services.feedback_learning_service import feedback_learning_service
from services.ssh_service import ssh_service
from services.command_template_service import command_template_service
from services.site_automation_service import site_automation_service
from api.schemas.automation import (
    TaskFeedbackRequest,
    TriggerDiagnosisRequest,
    TriggerAlertsRequest,
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
            "abnormal_type": sample.abnormal_type,
            "raw_data": sample.raw_data,
            "created_at": sample.created_at,
            "batch_id": sample.raw_data.get("batch_id") if isinstance(sample.raw_data, dict) else None
        }
        
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
    query = db.query(AutomationTask)

    if site_id:
        query = query.filter(AutomationTask.site_id == site_id)
    if status:
        query = query.filter(AutomationTask.status == status)
    
    # 时间范围筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(AutomationTask.created_at >= start_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format, use YYYY-MM-DD")
    
    if end_date:
        try:
            # 结束日期包含当天，所以加一天
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(AutomationTask.created_at < end_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format, use YYYY-MM-DD")

    total = query.count()
    tasks = query.order_by(AutomationTask.created_at.desc()).offset(skip).limit(limit).all()

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

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "returned": len(tasks_with_device_ip),
        "has_more": skip + len(tasks_with_device_ip) < total,
        "tasks": tasks_with_device_ip
    }


@router.get("/tasks/{task_id}")
async def get_automation_task(task_id: int, db: Session = Depends(get_db)):
    """获取自动化任务详情"""
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
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


@router.get("/tasks/{task_id}/feedback", response_model=TaskFeedbackListResponse)
async def get_task_feedback(task_id: int, db: Session = Depends(get_db)):
    """获取任务反馈列表"""
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

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
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    allowed_verdicts = {"correct", "incorrect", "partial"}
    if payload.verdict not in allowed_verdicts:
        raise HTTPException(status_code=400, detail="verdict must be one of correct|incorrect|partial")

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
        await automation_orchestrator.process_abnormal_sample(sample_id)
        return {
            "success": True,
            "message": f"Diagnosis triggered for sample {sample_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-alerts", response_model=ManualActionResponse)
async def trigger_alerts(
    payload: TriggerAlertsRequest,
    db: Session = Depends(get_db)
):
    """手动触发告警"""
    try:
        await alert_service.process_new_analysis_results(payload.site_id)
        return {
            "success": True,
            "message": "Alerts triggered successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolve-commands")
async def resolve_commands_for_device(
    device_id: int,
    template_type: str = "diagnosis_default",
    db: Session = Depends(get_db)
):
    """自动化中心：根据device_id和模板类型返回厂商命令集"""
    result = await command_template_service.resolve_commands_for_device(
        db=db,
        device_id=device_id,
        template_type=template_type,
    )
    return {"success": True, "data": result}
