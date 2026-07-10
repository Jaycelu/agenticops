from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from auth.session_service import privacy_digest
from models.auth import SecurityAuditEvent


AUDIT_LOCK_KEY = 4_105_774_321
REDACTED_KEY_PARTS = {
    "authorization",
    "cookie",
    "credential",
    "password",
    "private_key",
    "saml_response",
    "secret",
    "token",
}


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def calculate_event_hash(previous_hash: str | None, payload: dict[str, Any]) -> str:
    material = f"{previous_hash or ''}\n{canonical_json(payload)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def sanitize_audit_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 6:
        return "<max-depth>"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, child in list(value.items())[:100]:
            key = str(raw_key)
            normalized = key.lower()
            if any(part in normalized for part in REDACTED_KEY_PARTS):
                result[key] = "<redacted>"
            else:
                result[key] = sanitize_audit_value(child, depth=depth + 1)
        return result
    if isinstance(value, set):
        value = sorted(value, key=repr)
    if isinstance(value, (list, tuple)):
        return [sanitize_audit_value(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, str):
        return value[:4096]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:4096]


class SecurityAuditService:
    def append(
        self,
        db: Session,
        *,
        event_type: str,
        outcome: str,
        actor_user_id: int | None = None,
        actor_session_id: str | None = None,
        request_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        source_ip: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityAuditEvent:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": AUDIT_LOCK_KEY})

        previous = db.query(SecurityAuditEvent).order_by(SecurityAuditEvent.id.desc()).first()
        previous_hash = previous.event_hash if previous else None
        created_at = datetime.now(timezone.utc)
        safe_details = sanitize_audit_value(details or {})
        payload = {
            "event_type": event_type,
            "outcome": outcome,
            "actor_user_id": actor_user_id,
            "actor_session_id": actor_session_id,
            "request_id": request_id,
            "target_type": target_type,
            "target_id": target_id,
            "source_ip_hash": privacy_digest(source_ip),
            "details": safe_details,
            "created_at": created_at.isoformat(),
        }
        event = SecurityAuditEvent(
            **{key: value for key, value in payload.items() if key != "created_at"},
            previous_event_hash=previous_hash,
            event_hash=calculate_event_hash(previous_hash, payload),
            created_at=created_at,
        )
        db.add(event)
        db.flush()
        return event


security_audit_service = SecurityAuditService()
