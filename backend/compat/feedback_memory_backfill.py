from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session

from models.automation import AutomationTask, AutomationTaskFeedback
from services.memory_ingestion_service import memory_ingestion_service


def backfill_feedback_memories(db: Session, limit: int = 200) -> Dict[str, int]:
    rows = (
        db.query(AutomationTaskFeedback, AutomationTask)
        .join(AutomationTask, AutomationTaskFeedback.task_id == AutomationTask.id)
        .order_by(AutomationTaskFeedback.created_at.desc())
        .limit(limit)
        .all()
    )

    created = 0
    updated = 0
    for feedback, task in rows:
        key = f"feedback:{feedback.id}"
        payload = {
            "task_id": task.id,
            "task_code": task.task_code,
            "verdict": feedback.verdict,
            "reviewer": feedback.reviewer,
            "tags": feedback.tags or [],
            "comment": feedback.comment,
            "decision_result": task.decision_result or {},
            "trigger_event": task.trigger_event or {},
        }
        entry, was_created = memory_ingestion_service.remember_feedback(
            db,
            case_id=None,
            memory_key=key,
            title=f"反馈记忆 {task.task_code}",
            summary=feedback.comment or ((task.decision_result or {}).get("diagnosis") or {}).get("summary") or "",
            source="backfill_feedback",
            tags=feedback.tags or [],
            confidence=0.75 if feedback.verdict == "correct" else 0.45,
            success_score=1.0 if feedback.verdict == "correct" else 0.3,
            content=payload,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    db.commit()
    return {"limit": limit, "created": created, "updated": updated}
