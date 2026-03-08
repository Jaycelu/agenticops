from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from compat.automation_task_views import get_legacy_task_or_plan, list_plan_feedback_entries, parse_optional_date
from models.automation import AutomationTaskFeedback
from services.feedback_learning_service import feedback_learning_service


def get_compat_task_feedback(db: Session, task_id: int) -> Dict[str, Any]:
    task, plan = get_legacy_task_or_plan(db, task_id)
    if task is None and plan is None:
        raise LookupError("Task not found")

    if plan is not None:
        feedbacks = list_plan_feedback_entries(db, plan)
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
                "created_at": feedback.created_at,
            }
            for feedback in feedbacks
        ],
    }


def get_compat_feedback_stats(
    db: Session,
    *,
    diagnosis_type: Optional[str] = None,
    site_id: Optional[int] = None,
    window_days: int = 30,
    min_samples: int = 5,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start_datetime = parse_optional_date(start_date) if start_date else None
    end_datetime = parse_optional_date(end_date) + timedelta(days=1) if end_date else None
    stats = feedback_learning_service.get_feedback_stats(
        db=db,
        diagnosis_type=diagnosis_type,
        site_id=site_id,
        window_days=window_days,
        min_samples=min_samples,
        start_date=start_datetime,
        end_date=end_datetime,
    )
    return {
        "total_types": len(stats),
        "stats": stats,
    }


def get_compat_feedback_trends(
    db: Session,
    *,
    diagnosis_type: Optional[str] = None,
    site_id: Optional[int] = None,
    window_days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start_datetime = parse_optional_date(start_date) if start_date else None
    end_datetime = parse_optional_date(end_date) + timedelta(days=1) if end_date else None
    return feedback_learning_service.get_feedback_trends(
        db=db,
        site_id=site_id,
        diagnosis_type=diagnosis_type,
        window_days=window_days,
        start_date=start_datetime,
        end_date=end_datetime,
    )


def get_compat_feedback_insights(
    db: Session,
    *,
    site_id: Optional[int] = None,
    window_days: int = 30,
    min_samples: int = 5,
    top_n: int = 5,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start_datetime = parse_optional_date(start_date) if start_date else None
    end_datetime = parse_optional_date(end_date) + timedelta(days=1) if end_date else None
    return feedback_learning_service.get_feedback_insights(
        db=db,
        site_id=site_id,
        window_days=window_days,
        min_samples=min_samples,
        start_date=start_datetime,
        end_date=end_datetime,
        top_n=top_n,
    )
