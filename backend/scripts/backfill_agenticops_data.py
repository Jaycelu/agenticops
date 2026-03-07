"""
将旧 AutomationTask / AutomationTaskFeedback 补迁到 AgenticOps 数据模型。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal
from models.agenticops import (
    CaseRecord,
    CaseStatus,
    MemoryEntry,
    MemoryType,
    RemediationPlan,
    RemediationPlanStatus,
    SourceEvent,
    SourceEventStatus,
)
from models.automation import AutomationTask, AutomationTaskFeedback


def map_case_status(task: AutomationTask) -> CaseStatus:
    status = (task.status or "").lower()
    if status in {"success"}:
        return CaseStatus.RESOLVED
    if status in {"failed", "aborted", "cancelled"}:
        return CaseStatus.ESCALATED
    if status in {"running"}:
        return CaseStatus.EXECUTING
    if status in {"waiting_confirm", "waiting_approval"}:
        return CaseStatus.PLANNED
    return CaseStatus.INVESTIGATING


def map_plan_status(task: AutomationTask) -> RemediationPlanStatus:
    status = (task.status or "").lower()
    if status == "success":
        return RemediationPlanStatus.SUCCEEDED
    if status == "failed":
        return RemediationPlanStatus.FAILED
    if status == "aborted":
        return RemediationPlanStatus.CANCELLED
    if status == "running":
        return RemediationPlanStatus.EXECUTING
    if status == "waiting_approval":
        return RemediationPlanStatus.PENDING_APPROVAL
    if status == "waiting_confirm":
        return RemediationPlanStatus.APPROVED
    return RemediationPlanStatus.DRAFT


def build_summary(task: AutomationTask) -> str:
    decision = task.decision_result or {}
    diagnosis = decision.get("diagnosis") or {}
    return (
        diagnosis.get("summary")
        or decision.get("summary")
        or (task.execution_result or {}).get("message")
        or f"Legacy automation task {task.task_code}"
    )


def ensure_source_event(db: Session, task: AutomationTask) -> SourceEvent:
    dedup_key = f"legacy-task:{task.id}"
    item = db.query(SourceEvent).filter(SourceEvent.dedup_key == dedup_key).first()
    if item is not None:
        return item

    decision = task.decision_result or {}
    context = decision.get("context") or {}
    trigger = task.trigger_event or {}
    item = SourceEvent(
        source_type="legacy_automation_task",
        source_system="AUTOMATION",
        external_event_id=str(task.id),
        dedup_key=dedup_key,
        site_id=task.site_id,
        netbox_device_id=task.netbox_device_id,
        device_ip=context.get("device_ip"),
        host=context.get("device_ip"),
        title=task.task_code,
        severity=((decision.get("diagnosis") or {}).get("severity") or "warning"),
        status=SourceEventStatus.CASE_CREATED,
        occurred_at=task.created_at or task.started_at or datetime.utcnow(),
        raw_payload={
            "trigger_event": trigger,
            "decision_result": decision,
            "execution_result": task.execution_result or {},
            "audit_trail": task.audit_trail or [],
        },
        normalized_payload={
            "task_code": task.task_code,
            "status": task.status,
            "triggered_by": task.triggered_by,
        },
    )
    db.add(item)
    db.flush()
    return item


def ensure_case_record(db: Session, task: AutomationTask, source_event: SourceEvent) -> CaseRecord:
    case_code = f"LEGACY-CASE-{task.id}"
    item = db.query(CaseRecord).filter(CaseRecord.case_code == case_code).first()
    if item is not None:
        return item

    decision = task.decision_result or {}
    context = decision.get("context") or {}
    item = CaseRecord(
        case_code=case_code,
        title=build_summary(task),
        summary=build_summary(task),
        source_event_id=source_event.id,
        site_id=task.site_id,
        netbox_device_id=task.netbox_device_id,
        device_ip=context.get("device_ip"),
        host=context.get("device_ip"),
        priority="P2" if (task.need_human_confirm or task.status in {"failed", "waiting_approval"}) else "P3",
        risk_level=((decision.get("diagnosis") or {}).get("risk_level") or "medium"),
        status=map_case_status(task),
        current_phase="legacy_backfill",
        case_metadata={
            "migrated_from": "automation_task",
            "legacy_task_id": task.id,
            "legacy_task_code": task.task_code,
            "triggered_by": task.triggered_by,
        },
        opened_at=task.created_at or task.started_at,
        last_activity_at=task.finished_at or task.updated_at or task.created_at,
        closed_at=task.finished_at if task.status in {"success", "failed", "aborted", "cancelled"} else None,
    )
    db.add(item)
    db.flush()
    return item


def ensure_remediation_plan(db: Session, task: AutomationTask, case: CaseRecord) -> RemediationPlan:
    plan_code = f"LEGACY-{task.task_code}"
    item = db.query(RemediationPlan).filter(RemediationPlan.plan_code == plan_code).first()
    if item is not None:
        return item

    decision = task.decision_result or {}
    item = RemediationPlan(
        case_id=case.id,
        plan_code=plan_code,
        status=map_plan_status(task),
        execution_mode="manual" if task.need_human_confirm else "auto",
        approval_status="pending" if task.status == "waiting_approval" else ("approved" if task.status == "waiting_confirm" else "not_required"),
        risk_level=((decision.get("diagnosis") or {}).get("risk_level") or "medium"),
        summary=build_summary(task),
        plan_payload={
            "migrated_from": "automation_task",
            "legacy_task_id": task.id,
            "legacy_task_code": task.task_code,
            "decision_result": decision,
        },
        rollback_payload={},
        safety_checks={
            "legacy_status": task.status,
            "need_human_confirm": bool(task.need_human_confirm),
            "audit_trail": task.audit_trail or [],
        },
        approved_at=task.updated_at if task.status in {"waiting_confirm", "success"} else None,
        created_at=task.created_at,
    )
    db.add(item)
    db.flush()
    return item


def ensure_episode_memory(db: Session, task: AutomationTask, case: CaseRecord) -> bool:
    key = f"legacy-task-episode:{task.id}"
    entry = db.query(MemoryEntry).filter(MemoryEntry.memory_key == key).first()
    if entry is not None:
        return False

    db.add(
        MemoryEntry(
            case_id=case.id,
            memory_type=MemoryType.EPISODE,
            memory_key=key,
            title=f"Legacy Task Episode {task.task_code}",
            summary=build_summary(task),
            source="backfill_legacy_task",
            tags=[task.status or "unknown", task.triggered_by or "legacy"],
            confidence=0.7,
            success_score=1.0 if task.status == "success" else 0.3,
            content={
                "legacy_task_id": task.id,
                "legacy_task_code": task.task_code,
                "trigger_event": task.trigger_event or {},
                "decision_result": task.decision_result or {},
                "execution_result": task.execution_result or {},
            },
        )
    )
    return True


def ensure_feedback_memory(db: Session, task: AutomationTask, case: CaseRecord, feedback: AutomationTaskFeedback) -> bool:
    key = f"legacy-task-feedback:{feedback.id}"
    entry = db.query(MemoryEntry).filter(MemoryEntry.memory_key == key).first()
    if entry is not None:
        return False

    db.add(
        MemoryEntry(
            case_id=case.id,
            memory_type=MemoryType.FEEDBACK,
            memory_key=key,
            title=f"Legacy Feedback {task.task_code}",
            summary=feedback.comment or build_summary(task),
            source="backfill_legacy_feedback",
            tags=feedback.tags or [],
            confidence=0.75 if feedback.verdict == "correct" else 0.45,
            success_score=1.0 if feedback.verdict == "correct" else 0.3,
            content={
                "legacy_task_id": task.id,
                "legacy_task_code": task.task_code,
                "feedback_id": feedback.id,
                "verdict": feedback.verdict,
                "comment": feedback.comment,
                "reviewer": feedback.reviewer,
                "tags": feedback.tags or [],
            },
        )
    )
    return True


def run(limit: Optional[int], dry_run: bool) -> None:
    db = SessionLocal()
    try:
        query = db.query(AutomationTask).order_by(AutomationTask.created_at.asc())
        if limit:
            query = query.limit(limit)
        tasks = query.all()

        counters = {
            "tasks_seen": len(tasks),
            "source_events_created": 0,
            "cases_created": 0,
            "plans_created": 0,
            "episode_memories_created": 0,
            "feedback_memories_created": 0,
        }

        for task in tasks:
            source_before = db.query(SourceEvent).filter(SourceEvent.dedup_key == f"legacy-task:{task.id}").first()
            case_before = db.query(CaseRecord).filter(CaseRecord.case_code == f"LEGACY-CASE-{task.id}").first()
            plan_before = db.query(RemediationPlan).filter(RemediationPlan.plan_code == f"LEGACY-{task.task_code}").first()

            source_event = ensure_source_event(db, task)
            case = ensure_case_record(db, task, source_event)
            ensure_remediation_plan(db, task, case)

            if source_before is None:
                counters["source_events_created"] += 1
            if case_before is None:
                counters["cases_created"] += 1
            if plan_before is None:
                counters["plans_created"] += 1
            if ensure_episode_memory(db, task, case):
                counters["episode_memories_created"] += 1

            for feedback in task.feedbacks or []:
                if ensure_feedback_memory(db, task, case, feedback):
                    counters["feedback_memories_created"] += 1

        if dry_run:
            db.rollback()
            print({"dry_run": True, **counters})
            return

        db.commit()
        print({"dry_run": False, **counters})
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill legacy automation data into AgenticOps tables")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of AutomationTask rows to process")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing changes")
    args = parser.parse_args()
    try:
        run(limit=args.limit, dry_run=args.dry_run)
    except SQLAlchemyError as exc:
        raise SystemExit(f"Database connection or query failed: {exc}") from exc


if __name__ == "__main__":
    main()
