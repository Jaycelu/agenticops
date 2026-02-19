import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.common import MessageResponse, PageMeta
from api.schemas.events import (
    EDAIngestResponse,
    EDAWebhookRequest,
    EventDispatchRequest,
    EventDispatchResponse,
    EventIngestRequest,
    EventIngestResponse,
    EventListResponse,
    EventPlaybookDraftRequest,
    EventPlaybookDraftResponse,
    EventRelationsResponse,
    SplunkWebhookRequest,
    EventTicketCreateRequest,
    EventTicketResponse,
)
from config.settings import settings
from database import get_db
from models.automation import AlertEvent, AutomationTask, LocalTicket
from services.decision_service import decision_service
from services.event_skill_service import event_skill_service
from services.playbook_draft_service import playbook_draft_service
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


def _pick_first(*values: Any) -> Optional[Any]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _parse_optional_datetime(raw: Any) -> Optional[datetime]:
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        if raw > 10_000_000_000:
            return datetime.fromtimestamp(raw / 1000)
        return datetime.fromtimestamp(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if text.isdigit():
            return _parse_optional_datetime(int(text))
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _build_event_from_splunk(payload: SplunkWebhookRequest) -> EventIngestRequest:
    body = payload.result or payload.event or {}
    severity = str(_pick_first(body.get("severity"), body.get("priority"), body.get("level"), "warning")).lower()
    external_event_id = str(
        _pick_first(
            body.get("event_id"),
            body.get("alert_id"),
            body.get("sid"),
            payload.sid,
        )
        or ""
    ) or None
    site_id_raw = _pick_first(body.get("site_id"), body.get("siteId"))
    netbox_device_id_raw = _pick_first(body.get("netbox_device_id"), body.get("netboxDeviceId"), body.get("device_id"))
    site_id = int(site_id_raw) if str(site_id_raw).isdigit() else None
    netbox_device_id = int(netbox_device_id_raw) if str(netbox_device_id_raw).isdigit() else None
    name = str(
        _pick_first(
            body.get("name"),
            body.get("title"),
            body.get("message"),
            payload.search_name,
            "splunk_event",
        )
    )
    host = _pick_first(body.get("host"), body.get("hostname"), payload.host)
    occurred_at = _parse_optional_datetime(_pick_first(body.get("occurred_at"), body.get("time"), payload.time))
    fingerprint = str(_pick_first(body.get("fingerprint"), payload.sid, external_event_id) or "")
    event_type = str(_pick_first(body.get("event_type"), body.get("eventType"), "splunk_alert"))

    return EventIngestRequest(
        source="SPLUNK",
        event_type=event_type,
        external_event_id=external_event_id,
        site_id=site_id,
        netbox_device_id=netbox_device_id,
        host=str(host) if host is not None else None,
        name=name,
        severity=severity,
        occurred_at=occurred_at,
        fingerprint=fingerprint or None,
        tags=["splunk", str(event_type)],
        raw_payload=payload.model_dump(),
    )


def _build_event_from_eda(payload: EDAWebhookRequest) -> EventIngestRequest:
    body = payload.event or {}
    metadata = payload.metadata or {}
    external_event_id = str(
        _pick_first(
            payload.event_id,
            body.get("event_id"),
            body.get("id"),
            metadata.get("event_id"),
        )
        or ""
    ) or None
    event_type = str(_pick_first(body.get("event_type"), metadata.get("event_type"), "eda_rule_match"))
    severity = str(_pick_first(payload.severity, body.get("severity"), metadata.get("severity"), "warning")).lower()
    site_id_raw = _pick_first(body.get("site_id"), metadata.get("site_id"))
    netbox_device_id_raw = _pick_first(body.get("netbox_device_id"), metadata.get("netbox_device_id"))
    site_id = int(site_id_raw) if str(site_id_raw).isdigit() else None
    netbox_device_id = int(netbox_device_id_raw) if str(netbox_device_id_raw).isdigit() else None
    host = _pick_first(body.get("host"), body.get("hostname"), metadata.get("host"))
    name = str(_pick_first(body.get("name"), body.get("title"), payload.rule_name, "eda_event"))
    occurred_at = _parse_optional_datetime(_pick_first(payload.occurred_at, body.get("time"), metadata.get("time")))

    return EventIngestRequest(
        source="EDA",
        event_type=event_type,
        external_event_id=external_event_id,
        site_id=site_id,
        netbox_device_id=netbox_device_id,
        host=str(host) if host is not None else None,
        name=name,
        severity=severity,
        occurred_at=occurred_at,
        fingerprint=str(_pick_first(metadata.get("fingerprint"), external_event_id, payload.rule_name) or "") or None,
        tags=["eda", str(event_type), str(payload.rulebook or "rulebook")],
        raw_payload=payload.model_dump(),
    )


async def _dispatch_readonly_for_event(event: AlertEvent, reviewer: str, db: Session) -> Dict[str, Any]:
    if event.site_id is None:
        return {"success": False, "task_id": None, "message": "Event missing site_id, skip auto dispatch"}

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
        return {"success": False, "task_id": None, "message": "Failed to create task"}

    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if task:
        playbook_draft = playbook_draft_service.generate_for_event(event)
        task.audit_trail = built["audit_trail"]
        task.audit_trail.append(
            {
                "stage": "PlaybookDraft",
                "title": "生成并校验Playbook草稿（check模式）",
                "payload": {
                    "check": playbook_draft.get("check", {}),
                    "playbook_yaml": playbook_draft.get("playbook_yaml", ""),
                    "observe_only": True,
                },
            }
        )
        decision_payload = task.decision_result or {}
        decision_context = decision_payload.get("context") or {}
        decision_context["playbook_draft"] = {
            "check": playbook_draft.get("check", {}),
            "generated_at": datetime.now().isoformat(),
        }
        decision_payload["context"] = decision_context
        task.decision_result = decision_payload
        event_payload = dict(event.payload or {})
        event_payload["task"] = {
            "task_id": task_id,
            "task_code": task.task_code,
            "status": "waiting_confirm",
            "created_at": datetime.now().isoformat(),
        }
        event_payload["playbook_draft"] = {
            "check": playbook_draft.get("check", {}),
            "generated_at": datetime.now().isoformat(),
        }
        event.payload = event_payload
        db.commit()

    await decision_service.update_task_status(
        task_id=task_id,
        status="waiting_confirm",
        execution_result=SchemaExecutionResult(
            status="success",
            message=f"只读研判任务已创建，等待人工确认（reviewer={reviewer}）",
            details={"event_id": event.id, "read_only": True},
        ),
    )
    return {
        "success": True,
        "task_id": task_id,
        "message": "Read-only diagnosis task created",
        "playbook_check": (event.payload or {}).get("playbook_draft", {}).get("check", {}),
    }


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


@router.post("/ingest/splunk", response_model=EventIngestResponse)
async def ingest_splunk_event(
    payload: SplunkWebhookRequest,
    x_splunk_token: Optional[str] = Header(default=None, alias="X-Splunk-Token"),
    db: Session = Depends(get_db),
):
    expected = (settings.splunk_webhook_token or "").strip()
    if expected and x_splunk_token != expected:
        raise HTTPException(status_code=401, detail="Invalid Splunk webhook token")

    mapped = _build_event_from_splunk(payload)
    record = _upsert_event(db, mapped)
    db.commit()
    db.refresh(record)
    return {
        "accepted": True,
        "observe_only": settings.automation_observe_only,
        "event": record,
    }


@router.post("/ingest/eda", response_model=EDAIngestResponse)
async def ingest_eda_event(
    payload: EDAWebhookRequest,
    x_eda_token: Optional[str] = Header(default=None, alias="X-EDA-Token"),
    db: Session = Depends(get_db),
):
    expected = (settings.eda_webhook_token or "").strip()
    if expected and x_eda_token != expected:
        raise HTTPException(status_code=401, detail="Invalid EDA webhook token")

    mapped = _build_event_from_eda(payload)
    record = _upsert_event(db, mapped)
    db.commit()
    db.refresh(record)

    dispatch_result = {"dispatched": False, "task_id": None, "message": "Auto dispatch disabled"}
    if payload.auto_dispatch_readonly:
        result = await _dispatch_readonly_for_event(record, reviewer=payload.reviewer or "eda-system", db=db)
        dispatch_result = {
            "dispatched": bool(result.get("success", False)),
            "task_id": result.get("task_id"),
            "message": result.get("message", ""),
        }

    return {
        "accepted": True,
        "observe_only": settings.automation_observe_only,
        "event": record,
        "dispatch": dispatch_result,
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

    result = await _dispatch_readonly_for_event(event, reviewer=payload.reviewer or "system", db=db)
    return {
        "success": bool(result.get("success", False)),
        "message": result.get("message", ""),
        "task_id": result.get("task_id"),
        "playbook_check": result.get("playbook_check", {}),
    }


@router.post("/{event_id}/playbook-draft-check", response_model=EventPlaybookDraftResponse)
async def generate_event_playbook_draft(
    event_id: int,
    payload: EventPlaybookDraftRequest,
    db: Session = Depends(get_db),
):
    event = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
    if not event:
        return {
            "success": False,
            "message": "Event not found",
            "event_id": event_id,
            "playbook_check": {"passed": False, "errors": ["event_not_found"], "warnings": []},
            "playbook_yaml": "",
        }

    draft = playbook_draft_service.generate_for_event(event)
    event_payload = dict(event.payload or {})
    event_payload["playbook_draft"] = {
        "check": draft.get("check", {}),
        "generated_at": datetime.now().isoformat(),
    }
    event.payload = event_payload
    db.commit()

    return {
        "success": True,
        "message": "Playbook draft generated",
        "event_id": event_id,
        "playbook_check": draft.get("check", {}),
        "playbook_yaml": draft.get("playbook_yaml", "") if payload.include_playbook else "",
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

    if (settings.ticket_mode or "local").lower() != "external" or not settings.ticket_system_base_url:
        ticket_code = f"LOCAL-{int(datetime.now().timestamp() * 1000)}"
        local_ticket = LocalTicket(
            ticket_code=ticket_code,
            provider="local",
            event_id=event.id,
            title=ticket_payload["title"],
            description=ticket_payload["description"],
            priority=ticket_payload.get("priority") or "P3",
            requester=ticket_payload.get("requester") or "netops-automation",
            status="open",
            ticket_metadata=ticket_payload.get("metadata") or {},
        )
        db.add(local_ticket)
        db.flush()
        result = {
            "success": True,
            "ticket_id": ticket_code,
            "status": local_ticket.status,
            "provider": "local",
            "local_ticket_id": local_ticket.id,
        }
    else:
        result = await ticket_adapter.create_ticket(ticket_payload)

    event_payload = dict(event.payload or {})
    event_payload["ticket"] = {
        "ticket_id": result.get("ticket_id"),
        "provider": result.get("provider"),
        "status": result.get("status"),
        "local_ticket_id": result.get("local_ticket_id"),
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

    ticket_info = (event.payload or {}).get("ticket") or {}
    ticket_code = ticket_info.get("ticket_id")
    if ticket_code:
        try:
            local_ticket = db.query(LocalTicket).filter(LocalTicket.ticket_code == str(ticket_code)).first()
            if local_ticket:
                ticket_info = {
                    "ticket_id": local_ticket.ticket_code,
                    "provider": local_ticket.provider,
                    "status": local_ticket.status,
                    "priority": local_ticket.priority,
                    "requester": local_ticket.requester,
                    "created_at": local_ticket.created_at.isoformat() if local_ticket.created_at else None,
                    "updated_at": local_ticket.updated_at.isoformat() if local_ticket.updated_at else None,
                }
        except Exception:
            ticket_info = ticket_info

    return {
        "event_id": event_id,
        "ticket": ticket_info,
        "linked_tasks": linked,
    }
