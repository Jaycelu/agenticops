from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from compat.automation_task_views import parse_optional_date
from models.agenticops import CaseRecord, RemediationPlan, RemediationPlanStatus
from models.automation import AutomationTask, LogAnalysisResult, LogSample, Site
from services.feedback_learning_service import feedback_learning_service


def get_compat_dashboard_summary(
    db: Session,
    *,
    site_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start_datetime = parse_optional_date(start_date) if start_date else None
    end_datetime = parse_optional_date(end_date) + timedelta(days=1) if end_date else None

    sites_count = db.query(Site).count()

    samples_query = db.query(LogSample)
    if site_id:
        samples_query = samples_query.filter(LogSample.site_id == site_id)
    if start_datetime:
        samples_query = samples_query.filter(LogSample.sampled_at >= start_datetime)
    if end_datetime:
        samples_query = samples_query.filter(LogSample.sampled_at < end_datetime)
    samples_count = samples_query.count()
    abnormal_samples_count = samples_query.filter(LogSample.is_abnormal == True).count()

    analysis_query = db.query(LogAnalysisResult)
    if site_id:
        analysis_query = analysis_query.filter(LogAnalysisResult.site_id == site_id)
    if start_datetime:
        analysis_query = analysis_query.filter(LogAnalysisResult.created_at >= start_datetime)
    if end_datetime:
        analysis_query = analysis_query.filter(LogAnalysisResult.created_at < end_datetime)
    analysis_count = analysis_query.count()
    critical_count = analysis_query.filter(LogAnalysisResult.severity == "critical").count()
    warning_count = analysis_query.filter(LogAnalysisResult.severity == "warning").count()

    tasks_query = db.query(AutomationTask)
    if site_id:
        tasks_query = tasks_query.filter(AutomationTask.site_id == site_id)
    if start_datetime:
        tasks_query = tasks_query.filter(AutomationTask.created_at >= start_datetime)
    if end_datetime:
        tasks_query = tasks_query.filter(AutomationTask.created_at < end_datetime)
    tasks_count = tasks_query.count()
    running_tasks_count = tasks_query.filter(AutomationTask.status == "running").count()
    success_tasks_count = tasks_query.filter(AutomationTask.status == "success").count()
    failed_tasks_count = tasks_query.filter(AutomationTask.status == "failed").count()

    plan_query = db.query(RemediationPlan).join(CaseRecord, RemediationPlan.case_id == CaseRecord.id)
    if site_id:
        plan_query = plan_query.filter(CaseRecord.site_id == site_id)
    if start_datetime:
        plan_query = plan_query.filter(RemediationPlan.created_at >= start_datetime)
    if end_datetime:
        plan_query = plan_query.filter(RemediationPlan.created_at < end_datetime)
    tasks_count += plan_query.count()
    running_tasks_count += plan_query.filter(RemediationPlan.status == RemediationPlanStatus.EXECUTING).count()
    success_tasks_count += plan_query.filter(RemediationPlan.status == RemediationPlanStatus.SUCCEEDED).count()
    failed_tasks_count += plan_query.filter(RemediationPlan.status == RemediationPlanStatus.FAILED).count()

    try:
        feedback_stats = feedback_learning_service.get_feedback_stats(db=db, site_id=site_id)
    except Exception:
        feedback_stats = {}
    feedback_total = sum(item.get("total", 0) for item in feedback_stats.values())
    feedback_correct = sum(item.get("correct", 0) for item in feedback_stats.values())
    feedback_incorrect = sum(item.get("incorrect", 0) for item in feedback_stats.values())
    feedback_partial = sum(item.get("partial", 0) for item in feedback_stats.values())

    return {
        "sites": {"total": sites_count},
        "samples": {
            "total": samples_count,
            "abnormal": abnormal_samples_count,
            "abnormal_rate": round(abnormal_samples_count / samples_count * 100, 2) if samples_count > 0 else 0,
        },
        "analysis": {
            "total": analysis_count,
            "critical": critical_count,
            "warning": warning_count,
            "info": analysis_count - critical_count - warning_count,
        },
        "tasks": {
            "total": tasks_count,
            "running": running_tasks_count,
            "success": success_tasks_count,
            "failed": failed_tasks_count,
            "success_rate": round(success_tasks_count / tasks_count * 100, 2) if tasks_count > 0 else 0,
        },
        "feedback": {
            "total": feedback_total,
            "correct": feedback_correct,
            "incorrect": feedback_incorrect,
            "partial": feedback_partial,
            "correct_rate": round(feedback_correct / feedback_total * 100, 2) if feedback_total > 0 else 0,
            "incorrect_rate": round(feedback_incorrect / feedback_total * 100, 2) if feedback_total > 0 else 0,
        },
    }


def get_compat_dashboard_hourly_trends(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    target_day = date or datetime.now().strftime("%Y-%m-%d")
    target_date = datetime.strptime(target_day, "%Y-%m-%d")
    start_datetime = target_date
    end_datetime = target_date + timedelta(days=1)

    samples_query = db.query(LogSample).filter(
        LogSample.sampled_at >= start_datetime,
        LogSample.sampled_at < end_datetime,
    )
    if site_id:
        samples_query = samples_query.filter(LogSample.site_id == site_id)
    samples = samples_query.order_by(LogSample.sampled_at).all()

    hourly_data = {
        i: {
            "hour": f"{i:02d}:00",
            "samples": 0,
            "abnormal": 0,
        }
        for i in range(24)
    }

    for sample in samples:
        hour = sample.sampled_at.hour
        hourly_data[hour]["samples"] += 1
        if sample.is_abnormal:
            hourly_data[hour]["abnormal"] += 1

    return {
        "date": target_day,
        "trends": list(hourly_data.values()),
    }


def get_compat_dashboard_trends(
    db: Session,
    *,
    site_id: Optional[int] = None,
    days: int = 7,
) -> Dict[str, Any]:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    samples_query = db.query(LogSample).filter(
        LogSample.sampled_at >= start_date,
        LogSample.sampled_at <= end_date,
    )
    if site_id:
        samples_query = samples_query.filter(LogSample.site_id == site_id)

    daily_stats = []
    for i in range(days):
        day_start = start_date + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        day_samples = samples_query.filter(
            LogSample.sampled_at >= day_start,
            LogSample.sampled_at < day_end,
        ).all()
        daily_stats.append(
            {
                "date": day_start.strftime("%Y-%m-%d"),
                "samples": len(day_samples),
                "abnormal": len([s for s in day_samples if s.is_abnormal]),
            }
        )

    return {
        "period": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "days": days,
        },
        "trends": daily_stats,
    }
