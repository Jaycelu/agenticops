"""
自动化中心API接口
提供自动化相关的REST API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from database import get_db
from models.automation import (
    Site, LogSample, LogAnalysisResult,
    AutomationPolicy, AutomationTask, AutomationTaskFeedback
)
from services.automation_orchestrator import automation_orchestrator
from services.alert_service import alert_service
from services.feedback_learning_service import feedback_learning_service

router = APIRouter(prefix="/api/automation", tags=["自动化中心"])


class TaskFeedbackRequest(BaseModel):
    verdict: str = Field(..., description="correct|incorrect|partial")
    comment: Optional[str] = None
    reviewer: Optional[str] = "operator"
    tags: Optional[List[str]] = Field(default_factory=list)


# ============ 基地管理 ============

@router.get("/sites")
async def get_sites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取所有基地列表"""
    sites = db.query(Site).offset(skip).limit(limit).all()
    return {
        "total": db.query(Site).count(),
        "sites": sites
    }


@router.get("/sites/{site_id}")
async def get_site(site_id: int, db: Session = Depends(get_db)):
    """获取基地详情"""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ============ 日志采样 ============

@router.get("/samples")
async def get_log_samples(
    site_id: Optional[int] = None,
    is_abnormal: Optional[bool] = None,
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    skip: int = 0,
    limit: int = 100,
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
            "created_at": sample.created_at
        }
        
        # 从raw_data中获取设备IP
        if sample.raw_data and "device_ip" in sample.raw_data:
            sample_dict["device_ip"] = sample.raw_data["device_ip"]
        
        samples_with_device_ip.append(sample_dict)

    return {
        "total": total,
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
    skip: int = 0,
    limit: int = 100,
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
        latest_feedback = db.query(AutomationTaskFeedback).filter(
            AutomationTaskFeedback.task_id == task.id
        ).order_by(AutomationTaskFeedback.created_at.desc()).first()

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
        
        # 从context中获取设备IP
        if task.decision_result and "context" in task.decision_result:
            context = task.decision_result["context"]
            if "device_ip" in context:
                task_dict["device_ip"] = context["device_ip"]
        
        tasks_with_device_ip.append(task_dict)

    return {
        "total": total,
        "tasks": tasks_with_device_ip
    }


@router.get("/tasks/{task_id}")
async def get_automation_task(task_id: int, db: Session = Depends(get_db)):
    """获取自动化任务详情"""
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    feedbacks = db.query(AutomationTaskFeedback).filter(
        AutomationTaskFeedback.task_id == task.id
    ).order_by(AutomationTaskFeedback.created_at.desc()).all()

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
    
    # 从context中获取设备IP
    if task.decision_result and "context" in task.decision_result:
        context = task.decision_result["context"]
        if "device_ip" in context:
            task_dict["device_ip"] = context["device_ip"]
    
    return task_dict


@router.get("/tasks/{task_id}/feedback")
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


@router.get("/feedback/stats")
async def get_feedback_stats(
    diagnosis_type: Optional[str] = None,
    site_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取反馈统计（按诊断类型聚合）"""
    stats = feedback_learning_service.get_feedback_stats(
        db=db,
        diagnosis_type=diagnosis_type,
        site_id=site_id
    )
    return {
        "total_types": len(stats),
        "stats": stats
    }


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


# ============ 手动触发 ============

@router.post("/trigger-diagnosis")
async def trigger_diagnosis(
    sample_id: int,
    db: Session = Depends(get_db)
):
    """手动触发研判"""
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


@router.post("/trigger-alerts")
async def trigger_alerts(
    site_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """手动触发告警"""
    try:
        await alert_service.process_new_analysis_results(site_id)
        return {
            "success": True,
            "message": "Alerts triggered successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
