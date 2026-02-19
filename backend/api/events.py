import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.schemas.common import MessageResponse, PageMeta
from api.schemas.events import (
    EventDispatchRequest,
    EventDispatchResponse,
    EventIngestRequest,
    EventIngestResponse,
    EventListResponse,
    EventRelationsResponse,
    EventTicketCreateRequest,
    EventTicketResponse,
)
from config.settings import settings
from database import get_db
from models.automation import AlertEvent, AutomationTask
from services.decision_service import decision_service
from services.event_skill_service import event_skill_service
from services.schemas import ExecutionResult as SchemaExecutionResult, TaskTriggerEvent
from services.ticket_adapter import ticket_adapter

router = APIRouter(prefix="/api/events", tags=["events"])


def _normalize_severity(severity: Optional[str], severity_level: Optional[int]) -> tuple[str, int]:
    if severity_level is None:
        mapped = {
            "critical": 5,
            "high": 4,
            "warning": 2,
            "warn": 2,
            "medium": 2,
            "info": 1,
            "low": 1,
        }
        severity_level = mapped.get((severity or "").lower(), 2)

    if not severity:
        level_to_name = {
            5: "critical",
            4: "high",
            3: "major",
            2: "warning",
            1: "info",
            0: "unknown",
        }
        severity = level_to_name.get(severity_level, "warning")

    return severity, severity_level


def _build_dedup_key(payload: EventIngestRequest) -> str:
    if payload.external_event_id:
        raw_key = f"{payload.source}|{payload.external_event_id}"
    elif payload.fingerprint:
        raw_key = f"{payload.source}|{payload.fingerprint}"
    else:
        bucket = datetime.utcnow().strftime("%Y%m%d%H%M")
        raw_key = f"{payload.source}|{payload.host}|{payload.name}|{bucket}"
    return hashlib.md5(raw_key.encode()).hexdigest()


def _upsert_event(db: Session, payload: EventIngestRequest) -> AlertEvent:
    dedup_key = _build_dedup_key(payload)
    record = db.query(AlertEvent).filter(AlertEvent.dedup_key == dedup_key).first()
    if not record:
        record = AlertEvent(dedup_key=dedup_key)
        # SQLite does not auto-increment BigInteger PK; assign manually for test/local sqlite mode.
        if db.bind is not None and db.bind.dialect.name == "sqlite":
            max_id = db.query(func.max(AlertEvent.id)).scalar()
            record.id = int(max_id or 0) + 1
        db.add(record)

    severity, severity_level = _normalize_severity(payload.severity, payload.severity_level)
    record.source = payload.source
    record.external_event_id = payload.external_event_id
    record.site_id = payload.site_id
    record.netbox_device_id = payload.netbox_device_id
    record.host = payload.host
    record.name = payload.name
    record.severity = severity
    record.severity_level = severity_level
    record.status = "open"
    record.acknowledged = False
    record.occurred_at = payload.occurred_at or datetime.now()
    record.last_seen_at = datetime.now()
    record.payload = {
        "event_type": payload.event_type,
        "fingerprint": payload.fingerprint,
        "tags": payload.tags,
        "raw": payload.raw_payload or {},
    }
    return record


@router.get("/mode", response_model=MessageResponse)
async def get_mode():
    mode = "observe_only" if settings.automation_observe_only else "normal"
    return {"message": mode}


@router.post("/ingest", response_model=EventIngestResponse)
async def ingest_event(payload: EventIngestRequest, db: Session = Depends(get_db)):
    record = _upsert_event(db, payload)
    db.commit()
    db.refresh(record)
    return {
        "accepted": True,
        "observe_only": settings.automation_observe_only,
        "event": record,
    }


@router.get("", response_model=EventListResponse)
async def list_events(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    site_id: Optional[int] = None,
    netbox_device_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(AlertEvent)
    if status:
        query = query.filter(AlertEvent.status == status)
    if severity:
        query = query.filter(AlertEvent.severity == severity)
    if source:
        query = query.filter(AlertEvent.source == source)
    if site_id is not None:
        query = query.filter(AlertEvent.site_id == site_id)
    if netbox_device_id is not None:
        query = query.filter(AlertEvent.netbox_device_id == netbox_device_id)

    total = query.count()
    records = query.order_by(AlertEvent.occurred_at.desc()).offset(skip).limit(limit).all()
    returned = len(records)

    return {
        "page": PageMeta(
            total=total,
            skip=skip,
            limit=limit,
            returned=returned,
            has_more=(skip + returned) < total,
        ),
        "events": records,
    }


@router.post("/{event_id}/dispatch-readonly", response_model=EventDispatchResponse)
async def dispatch_readonly_diagnosis(
    event_id: int,
    payload: EventDispatchRequest,
    db: Session = Depends(get_db),
):
    event = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
    if not event:
        return {"success": False, "message": "Event not found", "task_id": None}

    if event.site_id is None:
        return {"success": False, "message": "Event missing site_id, cannot dispatch task", "task_id": None}

    built = event_skill_service.build_decision_for_event(event)
    decision = built["decision"]
    trigger_event = TaskTriggerEvent(
        event_type="event",
        source_id=event.id,
        source_type="AlertEvent",
        data={
            "source": event.source,
            "name": event.name,
            "severity": event.severity,
            "host": event.host,
        },
    )

    task_id = await decision_service.create_decision_task(
        site_id=event.site_id,
        netbox_device_id=event.netbox_device_id,
        device_ip=event.host or "unknown",
        decision_result=decision,
        trigger_event=trigger_event,
        policy_id=None,
    )
    if not task_id:
        return {"success": False, "message": "Failed to create task", "task_id": None}

    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if task:
        task.audit_trail = built["audit_trail"]
        event_payload = event.payload or {}
        event_payload["task"] = {
            "task_id": task_id,
            "task_code": task.task_code,
            "status": "waiting_confirm",
            "created_at": datetime.now().isoformat(),
        }
        event.payload = event_payload
        db.commit()

    await decision_service.update_task_status(
        task_id=task_id,
        status="waiting_confirm",
        execution_result=SchemaExecutionResult(
            status="success",
            message=f"只读研判任务已创建，等待人工确认（reviewer={payload.reviewer}）",
            details={"event_id": event.id, "read_only": True},
        ),
    )

    return {
        "success": True,
        "message": "Read-only diagnosis task created",
        "task_id": task_id,
    }


@router.post("/{event_id}/ticket", response_model=EventTicketResponse)
async def create_event_ticket(
    event_id: int,
    payload: EventTicketCreateRequest,
    db: Session = Depends(get_db),
):
    event = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
    if not event:
        return {"success": False, "message": "Event not found", "ticket_id": None, "provider": None}

    ticket_payload = {
        "title": payload.title or f"[{event.severity}] {event.name}",
        "description": payload.description or f"source={event.source}, host={event.host}, event_id={event.id}",
        "priority": payload.priority,
        "requester": payload.requester,
        "metadata": {
            "event_id": event.id,
            "external_event_id": event.external_event_id,
            "site_id": event.site_id,
            "netbox_device_id": event.netbox_device_id,
            "severity": event.severity,
            "status": event.status,
        },
    }

    result = await ticket_adapter.create_ticket(ticket_payload)
    event_payload = event.payload or {}
    event_payload["ticket"] = {
        "ticket_id": result.get("ticket_id"),
        "provider": result.get("provider"),
        "status": result.get("status"),
        "created_at": datetime.now().isoformat(),
    }
    event.payload = event_payload
    db.commit()

    return {
        "success": bool(result.get("success", False)),
        "message": "Ticket created" if result.get("success") else "Ticket creation failed",
        "ticket_id": result.get("ticket_id"),
        "provider": result.get("provider"),
    }


@router.get("/{event_id}/relations", response_model=EventRelationsResponse)
async def get_event_relations(event_id: int, db: Session = Depends(get_db)):
    event = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
    if not event:
        return {"event_id": event_id, "ticket": {}, "linked_tasks": []}

    # Keep query DB-agnostic by filtering in python for JSON trigger_event fields.
    linked = []
    try:
        candidates = db.query(AutomationTask).order_by(AutomationTask.created_at.desc()).limit(500).all()
        for task in candidates:
            trigger = task.trigger_event or {}
            if trigger.get("source_type") == "AlertEvent" and trigger.get("source_id") == event_id:
                linked.append(
                    {
                        "task_id": task.id,
                        "task_code": task.task_code,
                        "status": task.status,
                        "created_at": task.created_at,
                    }
                )
    except Exception:
        # Test/minimal DB may not include automation_task table yet.
        linked = []

    return {
        "event_id": event_id,
        "ticket": (event.payload or {}).get("ticket") or {},
        "linked_tasks": linked,
    }
