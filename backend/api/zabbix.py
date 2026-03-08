from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from adapters.zabbix_adapter import zabbix_adapter
from database import get_db
from models.agenticops import SourceEvent, SourceEventStatus
from services.event_decision_service import event_decision_service
from services.source_event_projection import attach_event_projection, upsert_source_event

router = APIRouter(prefix="/api/zabbix", tags=["zabbix"])


def _parse_clock(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        timestamp = int(value)
        return datetime.fromtimestamp(timestamp).isoformat()
    except Exception:  # noqa: BLE001
        return None


def _normalize_alert(item: Dict[str, Any]) -> Dict[str, Any]:
    hosts = item.get("hosts") or []
    primary_host = hosts[0] if hosts else {}
    severity = int(item.get("severity") or 0)
    severity_names = {
        0: "not_classified",
        1: "info",
        2: "warning",
        3: "average",
        4: "high",
        5: "disaster",
    }
    return {
        "event_id": item.get("eventid"),
        "name": item.get("name") or "zabbix_problem",
        "severity": severity_names.get(severity, str(severity)),
        "severity_level": severity,
        "host": primary_host.get("host") or primary_host.get("name"),
        "host_name": primary_host.get("name"),
        "clock": _parse_clock(item.get("clock")),
        "acknowledged": bool(int(item.get("acknowledged") or 0)),
        "object_id": item.get("objectid"),
        "raw": item,
    }


def _upsert_zabbix_event(db: Session, alert: Dict[str, Any]) -> SourceEvent:
    host = alert.get("host") or alert.get("host_name")
    dedup_key = f"zabbix:{host}:{alert.get('event_id') or alert.get('object_id')}"
    payload: Dict[str, Any] = {}
    payload.update(
        {
            "event_type": "zabbix_alert",
            "source_category": "zabbix_alert",
            "signal_key": f"zabbix_alert:{host}:{alert.get('event_id')}",
            "summary": alert.get("name"),
            "raw": alert.get("raw") or {},
        }
    )

    source_event = upsert_source_event(
        db,
        dedup_key=f"event:{dedup_key}",
        source_type="zabbix_alert",
        source_system="ZABBIX",
        external_event_id=alert.get("event_id"),
        site_id=None,
        netbox_device_id=None,
        device_ip=host,
        host=host,
        title=alert.get("name") or "zabbix_problem",
        severity=alert.get("severity") or "warning",
        occurred_at=datetime.fromisoformat(alert["clock"]) if alert.get("clock") else datetime.now(),
        collected_at=datetime.now(),
        raw_payload=alert.get("raw") or {},
        normalized_payload={
            "severity": alert.get("severity") or "warning",
            "severity_level": int(alert.get("severity_level") or 0),
            "source_category": "zabbix_alert",
            "event_type": "zabbix_alert",
            "signal_key": f"zabbix_alert:{host}:{alert.get('event_id')}",
            "summary": alert.get("name"),
        },
        status=SourceEventStatus.CORRELATED if alert.get("acknowledged") else SourceEventStatus.NEW,
    )
    attach_event_projection(
        source_event,
        legacy_dedup_key=dedup_key,
        legacy_source="ZABBIX",
        name=alert.get("name") or "zabbix_problem",
        host=host,
        severity=alert.get("severity") or "warning",
        severity_level=int(alert.get("severity_level") or 0),
        status="acknowledged" if alert.get("acknowledged") else "open",
        acknowledged=bool(alert.get("acknowledged")),
        occurred_at=datetime.fromisoformat(alert["clock"]) if alert.get("clock") else datetime.now(),
        last_seen_at=datetime.now(),
        payload={**payload, "source_event_id": int(source_event.id) if source_event.id is not None else None},
    )
    return source_event

def _build_linked_source_event_info(item: Optional[SourceEvent]) -> Dict[str, Any]:
    if not item:
        return {}
    payload = dict(item.normalized_payload or {})
    case_info = event_decision_service.get_case_info(payload)
    ticket_info = event_decision_service.get_ticket_info(payload)
    decision = event_decision_service.evaluate_source_event(item)
    legacy_event_id = payload.get("legacy_event_id")
    return {
        "event_id": int(legacy_event_id or item.id),
        "source_event_id": int(item.id),
        "status": payload.get("legacy_status") or (item.status.value if hasattr(item.status, "value") else str(item.status)),
        "severity": item.severity,
        "disposition": decision.get("disposition"),
        "disposition_reason": decision.get("reason"),
        "case_id": case_info.get("case_id"),
        "case_code": case_info.get("case_code"),
        "ticket_id": ticket_info.get("ticket_id"),
    }


@router.get("/status")
async def get_zabbix_status():
    return {
        "configured": zabbix_adapter.available,
        "source": "zabbix",
        "message": "ok" if zabbix_adapter.available else "zabbix_not_configured",
    }


@router.get("/alerts")
async def list_zabbix_alerts(
    host: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    result = await zabbix_adapter.get_recent_alerts(host=host, limit=limit)
    alerts = [_normalize_alert(item) for item in (result.get("alerts") or [])]
    source_dedup_map = {}
    if alerts:
        dedup_keys = [
            f"zabbix:{item.get('host') or item.get('host_name')}:{item.get('event_id') or item.get('object_id')}"
            for item in alerts
        ]
        source_records = db.query(SourceEvent).filter(
            SourceEvent.dedup_key.in_([f"event:{key}" for key in dedup_keys])
        ).all()
        source_dedup_map = {
            record.dedup_key.removeprefix("event:"): record
            for record in source_records
        }

    by_severity: Dict[str, int] = {}
    enriched_alerts = []
    for item in alerts:
        key = item["severity"]
        by_severity[key] = by_severity.get(key, 0) + 1
        dedup_key = f"zabbix:{item.get('host') or item.get('host_name')}:{item.get('event_id') or item.get('object_id')}"
        linked_event = _build_linked_source_event_info(source_dedup_map.get(dedup_key))
        enriched_alerts.append(
            {
                **item,
                "linked_event": linked_event or None,
            }
        )
    return {
        "success": result.get("success", False),
        "configured": zabbix_adapter.available,
        "host": host,
        "limit": limit,
        "total": len(enriched_alerts),
        "by_severity": by_severity,
        "alerts": enriched_alerts,
        "error": result.get("error"),
    }


@router.post("/sync-alerts")
async def sync_zabbix_alerts_to_events(
    host: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    result = await zabbix_adapter.get_recent_alerts(host=host, limit=limit)
    alerts = [_normalize_alert(item) for item in (result.get("alerts") or [])]
    created = 0
    updated = 0
    for alert in alerts:
        dedup_key = f"zabbix:{alert.get('host') or alert.get('host_name')}:{alert.get('event_id') or alert.get('object_id')}"
        existing = db.query(SourceEvent).filter(SourceEvent.dedup_key == f"event:{dedup_key}").first()
        _upsert_zabbix_event(db, alert)
        if existing:
            updated += 1
        else:
            created += 1
    db.commit()
    return {
        "success": result.get("success", False),
        "configured": zabbix_adapter.available,
        "created": created,
        "updated": updated,
        "total": len(alerts),
        "error": result.get("error"),
    }
