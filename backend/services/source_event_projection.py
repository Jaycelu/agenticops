from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.agenticops import SourceEvent, SourceEventStatus


def build_event_shadow(source_event: SourceEvent) -> SimpleNamespace:
    payload = dict(source_event.normalized_payload or {})
    payload.setdefault("raw", source_event.raw_payload or {})
    event_status = payload.get("legacy_status")
    if not event_status:
        status_value = source_event.status.value if hasattr(source_event.status, "value") else str(source_event.status or "new")
        event_status = {
            "new": "open",
            "correlated": "acknowledged",
            "case_created": "acknowledged",
            "closed": "resolved",
        }.get(status_value, "open")

    return SimpleNamespace(
        id=int(source_event.legacy_event_id or source_event.id or 0),
        source=source_event.source_system,
        external_event_id=source_event.external_event_id,
        dedup_key=(source_event.dedup_key or "").removeprefix("event:"),
        site_id=source_event.site_id,
        netbox_device_id=source_event.netbox_device_id,
        host=source_event.host or source_event.device_ip,
        name=source_event.title,
        severity=source_event.severity,
        severity_level=int(payload.get("severity_level") or 0),
        status=str(event_status),
        acknowledged=bool(payload.get("legacy_acknowledged") or str(event_status) != "open"),
        occurred_at=source_event.occurred_at,
        resolved_at=_parse_optional_datetime(payload.get("legacy_resolved_at")),
        last_seen_at=_parse_optional_datetime(payload.get("legacy_last_seen_at")) or source_event.collected_at,
        payload=payload,
    )


def upsert_source_event(
    db: Session,
    *,
    dedup_key: str,
    source_type: str,
    source_system: str,
    external_event_id: Optional[str],
    site_id: Optional[int],
    netbox_device_id: Optional[int],
    device_ip: Optional[str],
    host: Optional[str],
    title: str,
    severity: str,
    occurred_at: Optional[datetime],
    collected_at: Optional[datetime],
    raw_payload: Optional[Dict[str, Any]] = None,
    normalized_payload: Optional[Dict[str, Any]] = None,
    status: SourceEventStatus = SourceEventStatus.NEW,
    legacy_event_id: Optional[int] = None,
) -> SourceEvent:
    item = db.query(SourceEvent).filter(SourceEvent.dedup_key == dedup_key).first()
    if item is None and legacy_event_id is not None:
        item = db.query(SourceEvent).filter(SourceEvent.legacy_event_id == legacy_event_id).first()
    if item is None:
        item = SourceEvent(dedup_key=dedup_key)
        db.add(item)

    merged_normalized_payload = dict(item.normalized_payload or {})
    merged_normalized_payload.update(normalized_payload or {})

    payload_legacy_event_id = merged_normalized_payload.get("legacy_event_id")
    if legacy_event_id is None and payload_legacy_event_id not in (None, ""):
        try:
            legacy_event_id = int(payload_legacy_event_id)
        except (TypeError, ValueError):
            legacy_event_id = None

    item.legacy_event_id = legacy_event_id
    item.source_type = source_type
    item.source_system = source_system
    item.external_event_id = external_event_id
    item.site_id = site_id
    item.netbox_device_id = netbox_device_id
    item.device_ip = device_ip
    item.host = host
    item.title = title
    item.severity = severity
    item.status = status
    item.occurred_at = occurred_at or datetime.utcnow()
    item.collected_at = collected_at or datetime.utcnow()
    item.raw_payload = raw_payload or {}
    item.normalized_payload = merged_normalized_payload
    return item


def attach_event_projection(
    source_event: SourceEvent,
    *,
    legacy_source: str,
    legacy_dedup_key: str,
    host: Optional[str],
    severity: str,
    severity_level: int,
    status: str,
    acknowledged: bool,
    occurred_at: Optional[datetime],
    last_seen_at: Optional[datetime],
    payload: Optional[Dict[str, Any]] = None,
    resolved_at: Optional[datetime] = None,
) -> SourceEvent:
    normalized_payload = dict(source_event.normalized_payload or {})
    normalized_payload.update(payload or {})
    normalized_payload.update(
        {
            "legacy_status": status,
            "legacy_acknowledged": bool(acknowledged),
            "legacy_resolved_at": resolved_at.isoformat() if resolved_at else None,
            "legacy_last_seen_at": (last_seen_at or source_event.collected_at or datetime.utcnow()).isoformat(),
            "severity": severity,
            "severity_level": severity_level,
        }
    )

    if source_event.legacy_event_id is None and source_event.id is not None:
        source_event.legacy_event_id = int(source_event.id)
    if source_event.legacy_event_id is not None:
        normalized_payload["legacy_event_id"] = int(source_event.legacy_event_id)

    source_event.source_system = legacy_source
    source_event.dedup_key = source_event.dedup_key or legacy_dedup_key
    source_event.host = host or source_event.host or source_event.device_ip
    source_event.severity = severity
    source_event.occurred_at = occurred_at or source_event.occurred_at or datetime.utcnow()
    source_event.collected_at = last_seen_at or source_event.collected_at or datetime.utcnow()
    source_event.normalized_payload = normalized_payload
    return source_event


def _parse_optional_datetime(raw: Any) -> Optional[datetime]:
    if raw in (None, ""):
        return None
    if isinstance(raw, datetime):
        return raw
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
