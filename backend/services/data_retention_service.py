"""
自动化数据保留与清理服务
"""
from datetime import datetime, timedelta
from typing import Dict
import logging

from database import SessionLocal
from config.settings import settings
from models.automation import (
    RawAnomaly,
    LogSample,
    LogAnalysisResult,
    AutomationTask,
    AutomationActionLog,
    AutomationApproval,
    AutomationTaskFeedback,
)

logger = logging.getLogger(__name__)


class DataRetentionService:
    def cleanup(self) -> Dict[str, int]:
        db = SessionLocal()
        now = datetime.now()
        summary = {
            "raw_anomaly": 0,
            "log_sample": 0,
            "log_analysis_result": 0,
            "automation_task": 0,
            "automation_action_log": 0,
            "automation_approval": 0,
            "automation_task_feedback": 0,
        }

        try:
            raw_cutoff = now - timedelta(days=settings.retention_raw_anomaly_days)
            sample_cutoff = now - timedelta(days=settings.retention_log_sample_days)
            analysis_cutoff = now - timedelta(days=settings.retention_analysis_days)
            task_cutoff = now - timedelta(days=settings.retention_automation_task_days)
            action_cutoff = now - timedelta(days=settings.retention_action_log_days)
            approval_cutoff = now - timedelta(days=settings.retention_approval_days)
            feedback_cutoff = now - timedelta(days=settings.retention_feedback_days)
            summary["raw_anomaly"] = db.query(RawAnomaly).filter(
                RawAnomaly.created_at < raw_cutoff
            ).delete(synchronize_session=False)

            summary["log_sample"] = db.query(LogSample).filter(
                LogSample.sampled_at < sample_cutoff
            ).delete(synchronize_session=False)

            summary["log_analysis_result"] = db.query(LogAnalysisResult).filter(
                LogAnalysisResult.created_at < analysis_cutoff
            ).delete(synchronize_session=False)

            summary["automation_action_log"] = db.query(AutomationActionLog).filter(
                AutomationActionLog.executed_at < action_cutoff
            ).delete(synchronize_session=False)

            summary["automation_approval"] = db.query(AutomationApproval).filter(
                AutomationApproval.created_at < approval_cutoff
            ).delete(synchronize_session=False)

            summary["automation_task_feedback"] = db.query(AutomationTaskFeedback).filter(
                AutomationTaskFeedback.created_at < feedback_cutoff
            ).delete(synchronize_session=False)

            summary["automation_task"] = db.query(AutomationTask).filter(
                AutomationTask.created_at < task_cutoff
            ).delete(synchronize_session=False)

            db.commit()
            logger.info("Data retention cleanup done: %s", summary)
            return summary
        except Exception:
            db.rollback()
            logger.exception("Data retention cleanup failed")
            raise
        finally:
            db.close()


data_retention_service = DataRetentionService()
