from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from models.automation import AutomationTask, AutomationTaskFeedback


def find_feedback_memory_hits(db: Session, tokens: set[str], limit: int = 5) -> List[Dict[str, Any]]:
    """
    兼容层：从 legacy automation feedback 中提取可供 case pipeline 参考的历史命中。

    该逻辑只保留在 compat 层，避免 CaseOrchestrator 直接依赖旧任务模型。
    """
    normalized_tokens = {token.lower() for token in tokens if token}
    if not normalized_tokens:
        return []

    rows = (
        db.query(AutomationTaskFeedback, AutomationTask)
        .join(AutomationTask, AutomationTaskFeedback.task_id == AutomationTask.id)
        .order_by(AutomationTaskFeedback.created_at.desc())
        .limit(50)
        .all()
    )

    matched: List[Dict[str, Any]] = []
    for feedback, task in rows:
        decision = task.decision_result or {}
        trigger = task.trigger_event or {}
        haystack = " ".join(
            [
                str(task.netbox_device_id or ""),
                str((decision.get("context") or {}).get("device_ip") or ""),
                str((decision.get("diagnosis") or {}).get("summary") or ""),
                str(trigger.get("event_type") or ""),
                str(feedback.comment or ""),
                " ".join(feedback.tags or []),
            ]
        ).lower()
        if any(token in haystack for token in normalized_tokens):
            matched.append(
                {
                    "id": f"feedback-{feedback.id}",
                    "memory_type": "feedback",
                    "title": f"历史反馈任务 {task.task_code}",
                    "summary": feedback.comment or (decision.get("diagnosis") or {}).get("summary") or "",
                    "confidence": 0.7 if feedback.verdict == "correct" else 0.45,
                    "success_score": 1.0 if feedback.verdict == "correct" else 0.3,
                    "content": {
                        "task_id": task.id,
                        "task_code": task.task_code,
                        "verdict": feedback.verdict,
                        "tags": feedback.tags or [],
                        "decision_result": decision,
                    },
                }
            )
        if len(matched) >= limit:
            break
    return matched[:limit]
