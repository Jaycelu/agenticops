"""
反馈学习服务
基于人工反馈对诊断结果进行轻量校准
"""
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

from models.automation import AutomationTask, AutomationTaskFeedback
from services.schemas import DiagnosisResult

logger = logging.getLogger(__name__)


class FeedbackLearningService:
    """反馈学习服务"""

    def get_feedback_stats(
        self,
        db: Session,
        diagnosis_type: Optional[str] = None,
        site_id: Optional[int] = None,
        limit: int = 500
    ) -> Dict:
        feedbacks = db.query(AutomationTaskFeedback).order_by(
            AutomationTaskFeedback.created_at.desc()
        ).limit(limit).all()

        stats = {}
        for feedback in feedbacks:
            task = db.query(AutomationTask).filter(AutomationTask.id == feedback.task_id).first()
            if not task:
                continue
            if site_id and task.site_id != site_id:
                continue

            diag = (task.decision_result or {}).get("diagnosis", {})
            diag_type = str(diag.get("diagnosis_type", "UNKNOWN"))
            if diagnosis_type and diag_type != diagnosis_type:
                continue

            if diag_type not in stats:
                stats[diag_type] = {
                    "total": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "partial": 0
                }

            stats[diag_type]["total"] += 1
            verdict = feedback.verdict
            if verdict in ("correct", "incorrect", "partial"):
                stats[diag_type][verdict] += 1

        for diag_type, item in stats.items():
            total = item["total"] or 1
            item["correct_rate"] = round(item["correct"] / total, 4)
            item["incorrect_rate"] = round(item["incorrect"] / total, 4)
            item["partial_rate"] = round(item["partial"] / total, 4)

        return stats

    def calibrate_diagnosis_with_feedback(
        self,
        db: Session,
        diagnosis: DiagnosisResult,
        site_id: Optional[int] = None
    ) -> DiagnosisResult:
        diagnosis_type = diagnosis.diagnosis_type.value
        stats_map = self.get_feedback_stats(
            db=db,
            diagnosis_type=diagnosis_type,
            site_id=site_id
        )

        if diagnosis_type not in stats_map:
            return diagnosis

        stats = stats_map[diagnosis_type]
        total = stats.get("total", 0)
        incorrect_rate = stats.get("incorrect_rate", 0.0)
        correct_rate = stats.get("correct_rate", 0.0)

        if total >= 5 and incorrect_rate >= 0.4:
            diagnosis.confidence = max(0.1, diagnosis.confidence * 0.7)
            diagnosis.require_human_confirm = True
            diagnosis.recommendations = diagnosis.recommendations + [
                "历史误判率较高，建议人工二次确认后执行。"
            ]
        elif total >= 5 and correct_rate >= 0.8:
            diagnosis.confidence = min(0.95, diagnosis.confidence + 0.1)

        return diagnosis


feedback_learning_service = FeedbackLearningService()
