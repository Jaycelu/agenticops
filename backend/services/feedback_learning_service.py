"""
反馈学习服务
基于人工反馈对诊断结果进行轻量校准
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from sqlalchemy.orm import Session

from models.automation import AutomationTask, AutomationTaskFeedback, Site
from config.site_config import get_feedback_learning_policy
from services.schemas import DiagnosisResult

logger = logging.getLogger(__name__)


class FeedbackLearningService:
    """反馈学习服务"""

    DEFAULT_WINDOW_DAYS = 30
    DEFAULT_MIN_SAMPLES = 5

    def _get_site_code(self, db: Session, site_id: Optional[int]) -> Optional[str]:
        if not site_id:
            return None
        site = db.query(Site).filter(Site.id == site_id).first()
        return site.site_code if site else None

    def _resolve_policy(
        self,
        db: Session,
        site_id: Optional[int] = None,
        diagnosis_type: Optional[str] = None,
        window_days: Optional[int] = None,
        min_samples: Optional[int] = None
    ) -> Dict:
        site_code = self._get_site_code(db, site_id)
        policy = get_feedback_learning_policy(site_code, diagnosis_type)

        if window_days is not None:
            policy["window_days"] = window_days
        if min_samples is not None:
            policy["min_samples"] = min_samples
        return policy

    def _query_feedback_with_tasks(
        self,
        db: Session,
        site_id: Optional[int] = None,
        window_days: int = DEFAULT_WINDOW_DAYS,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Tuple[AutomationTaskFeedback, AutomationTask]]:
        query = db.query(AutomationTaskFeedback, AutomationTask).join(
            AutomationTask,
            AutomationTaskFeedback.task_id == AutomationTask.id
        )

        if site_id:
            query = query.filter(AutomationTask.site_id == site_id)

        if start_date:
            query = query.filter(AutomationTaskFeedback.created_at >= start_date)
        if end_date:
            query = query.filter(AutomationTaskFeedback.created_at < end_date)
        if not start_date and not end_date and window_days > 0:
            start_time = datetime.now() - timedelta(days=window_days)
            query = query.filter(AutomationTaskFeedback.created_at >= start_time)

        return query.order_by(AutomationTaskFeedback.created_at.desc()).limit(limit).all()

    def get_feedback_stats(
        self,
        db: Session,
        diagnosis_type: Optional[str] = None,
        site_id: Optional[int] = None,
        limit: int = 1000,
        window_days: Optional[int] = None,
        min_samples: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        policy = self._resolve_policy(
            db=db,
            site_id=site_id,
            diagnosis_type=diagnosis_type,
            window_days=window_days,
            min_samples=min_samples
        )
        resolved_window_days = int(policy.get("window_days", self.DEFAULT_WINDOW_DAYS))
        resolved_min_samples = int(policy.get("min_samples", self.DEFAULT_MIN_SAMPLES))

        rows = self._query_feedback_with_tasks(
            db=db,
            site_id=site_id,
            window_days=resolved_window_days,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        stats = {}
        for feedback, task in rows:
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
            item["is_sample_sufficient"] = item["total"] >= resolved_min_samples
            item["window_days"] = resolved_window_days
            item["min_samples"] = resolved_min_samples
            item["start_date"] = start_date.isoformat() if start_date else None
            item["end_date"] = end_date.isoformat() if end_date else None

        return stats

    def get_feedback_trends(
        self,
        db: Session,
        site_id: Optional[int] = None,
        diagnosis_type: Optional[str] = None,
        window_days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 5000
    ) -> Dict:
        policy = self._resolve_policy(
            db=db,
            site_id=site_id,
            diagnosis_type=diagnosis_type,
            window_days=window_days
        )
        resolved_window_days = int(policy.get("window_days", self.DEFAULT_WINDOW_DAYS))

        rows = self._query_feedback_with_tasks(
            db=db,
            site_id=site_id,
            window_days=resolved_window_days,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        trends = {}
        for feedback, task in rows:
            diag = (task.decision_result or {}).get("diagnosis", {})
            diag_type = str(diag.get("diagnosis_type", "UNKNOWN"))
            if diagnosis_type and diag_type != diagnosis_type:
                continue

            day_key = feedback.created_at.strftime("%Y-%m-%d") if feedback.created_at else "unknown"
            trends.setdefault(diag_type, {})
            trends[diag_type].setdefault(day_key, {
                "date": day_key,
                "total": 0,
                "correct": 0,
                "incorrect": 0,
                "partial": 0
            })

            bucket = trends[diag_type][day_key]
            bucket["total"] += 1
            if feedback.verdict in ("correct", "incorrect", "partial"):
                bucket[feedback.verdict] += 1

        result = {}
        for diag_type, date_map in trends.items():
            points = list(date_map.values())
            points.sort(key=lambda x: x["date"])
            for point in points:
                total = point["total"] or 1
                point["correct_rate"] = round(point["correct"] / total, 4)
                point["incorrect_rate"] = round(point["incorrect"] / total, 4)
                point["partial_rate"] = round(point["partial"] / total, 4)
            result[diag_type] = points

        return {
            "window_days": resolved_window_days,
            "diagnosis_type": diagnosis_type,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "trends": result
        }

    def get_feedback_insights(
        self,
        db: Session,
        site_id: Optional[int] = None,
        window_days: Optional[int] = None,
        min_samples: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        top_n: int = 5
    ) -> Dict:
        stats = self.get_feedback_stats(
            db=db,
            site_id=site_id,
            window_days=window_days,
            min_samples=min_samples,
            start_date=start_date,
            end_date=end_date
        )

        sorted_types = sorted(
            stats.items(),
            key=lambda x: (x[1].get("incorrect_rate", 0.0), x[1].get("total", 0)),
            reverse=True
        )
        top_types = sorted_types[:top_n]

        insights = []
        for diag_type, item in top_types:
            suggestion = "维持当前策略"
            if not item.get("is_sample_sufficient"):
                suggestion = "样本不足，建议继续积累反馈再调整阈值"
            elif item.get("incorrect_rate", 0.0) >= 0.4:
                suggestion = "建议提升人工确认等级，并提高触发阈值或增加澄清步骤"
            elif item.get("correct_rate", 0.0) >= 0.8:
                suggestion = "建议保持自动化策略，可适度降低人工确认频次"

            insights.append({
                "diagnosis_type": diag_type,
                "total": item.get("total", 0),
                "incorrect_rate": item.get("incorrect_rate", 0.0),
                "correct_rate": item.get("correct_rate", 0.0),
                "is_sample_sufficient": item.get("is_sample_sufficient", False),
                "suggestion": suggestion
            })

        return {
            "top_n": top_n,
            "insights": insights
        }

    def calibrate_diagnosis_with_feedback(
        self,
        db: Session,
        diagnosis: DiagnosisResult,
        site_id: Optional[int] = None,
        window_days: Optional[int] = None,
        min_samples: Optional[int] = None
    ) -> DiagnosisResult:
        diagnosis_type = diagnosis.diagnosis_type.value
        policy = self._resolve_policy(
            db=db,
            site_id=site_id,
            diagnosis_type=diagnosis_type,
            window_days=window_days,
            min_samples=min_samples
        )
        resolved_window_days = int(policy.get("window_days", self.DEFAULT_WINDOW_DAYS))
        resolved_min_samples = int(policy.get("min_samples", self.DEFAULT_MIN_SAMPLES))
        incorrect_threshold = float(policy.get("incorrect_rate_threshold", 0.4))
        correct_threshold = float(policy.get("correct_rate_threshold", 0.8))
        decrease_factor = float(policy.get("confidence_decrease_factor", 0.7))
        increase_value = float(policy.get("confidence_increase_value", 0.1))

        stats_map = self.get_feedback_stats(
            db=db,
            diagnosis_type=diagnosis_type,
            site_id=site_id,
            window_days=resolved_window_days,
            min_samples=resolved_min_samples
        )

        if diagnosis_type not in stats_map:
            return diagnosis

        stats = stats_map[diagnosis_type]
        total = stats.get("total", 0)
        incorrect_rate = stats.get("incorrect_rate", 0.0)
        correct_rate = stats.get("correct_rate", 0.0)

        if total >= resolved_min_samples and incorrect_rate >= incorrect_threshold:
            diagnosis.confidence = max(0.1, diagnosis.confidence * decrease_factor)
            diagnosis.require_human_confirm = True
            diagnosis.recommendations = diagnosis.recommendations + [
                "历史误判率较高，建议人工二次确认后执行。"
            ]
        elif total >= resolved_min_samples and correct_rate >= correct_threshold:
            diagnosis.confidence = min(0.95, diagnosis.confidence + increase_value)

        return diagnosis


feedback_learning_service = FeedbackLearningService()
