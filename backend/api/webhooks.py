from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from audit.service import security_audit_service
from auth.dependencies import require_permissions
from auth.rbac import Permission
from auth.schemas import Principal
from database import get_db
from models.webhook import OutboxEvent, WebhookDelivery, WebhookEndpoint
from webhooks.security import encrypt_endpoint_secret, secret_fingerprint, validate_webhook_url
from webhooks.service import webhook_service
from config.settings import settings


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class EndpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=2048)
    enabled: bool = True
    event_types: list[str] = Field(min_length=1, max_length=100)
    secret: str | None = Field(default=None, min_length=24, max_length=512)
    timeout_seconds: int = Field(default=10, ge=1, le=30)
    max_attempts: int = Field(default=8, ge=1, le=20)


def endpoint_view(row: WebhookEndpoint) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "name": row.name,
        "url": row.url,
        "enabled": row.enabled,
        "event_types": row.event_types or [],
        "secret_fingerprint": row.secret_fingerprint,
        "timeout_seconds": row.timeout_seconds,
        "max_attempts": row.max_attempts,
        "updated_at": row.updated_at,
    }


@router.get("/endpoints")
def list_endpoints(
    principal: Principal = Depends(require_permissions(Permission.WEBHOOKS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    del principal
    return {"items": [endpoint_view(row) for row in db.query(WebhookEndpoint).order_by(WebhookEndpoint.name).all()]}


@router.put("/endpoints/{endpoint_id}")
def upsert_endpoint(
    endpoint_id: int,
    payload: EndpointRequest,
    principal: Principal = Depends(require_permissions(Permission.WEBHOOKS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    try:
        validated = validate_webhook_url(payload.url, allow_http=settings.webhook_allow_http)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    row = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first() if endpoint_id > 0 else None
    if row is None:
        if endpoint_id > 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="endpoint not found")
        if not payload.secret:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="secret is required for a new endpoint")
        row = WebhookEndpoint(
            name=payload.name.strip(),
            url=validated.url,
            enabled=payload.enabled,
            event_types=sorted(set(payload.event_types)),
            secret_encrypted="pending",
            secret_fingerprint="pending",
            timeout_seconds=payload.timeout_seconds,
            max_attempts=payload.max_attempts,
            created_by_user_id=principal.user_id,
        )
        db.add(row)
        db.flush()
    else:
        row.name = payload.name.strip()
        row.url = validated.url
        row.enabled = payload.enabled
        row.event_types = sorted(set(payload.event_types))
        row.timeout_seconds = payload.timeout_seconds
        row.max_attempts = payload.max_attempts
    if payload.secret:
        row.secret_encrypted = encrypt_endpoint_secret(row, payload.secret)
        row.secret_fingerprint = secret_fingerprint(payload.secret)
    security_audit_service.append(
        db,
        event_type="webhook.endpoint.updated",
        outcome="success",
        actor_user_id=principal.user_id,
        actor_session_id=principal.session_id,
        target_type="webhook_endpoint",
        target_id=str(row.id),
        details={"enabled": row.enabled, "event_types": row.event_types, "secret_rotated": bool(payload.secret)},
    )
    db.commit()
    db.refresh(row)
    return endpoint_view(row)


@router.post("/endpoints/{endpoint_id}/test")
def test_endpoint(
    endpoint_id: int,
    principal: Principal = Depends(require_permissions(Permission.WEBHOOKS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id, WebhookEndpoint.enabled.is_(True)).first()
    if endpoint is None:
        raise HTTPException(status_code=404, detail="enabled endpoint not found")
    event = webhook_service.enqueue(
        db,
        event_type="webhook.test",
        aggregate_type="webhook_endpoint",
        aggregate_id=str(endpoint_id),
        payload={"requested_by_user_id": principal.user_id, "message": "AgenticOps webhook test"},
        endpoint_ids={endpoint_id},
    )
    db.commit()
    return {"event_id": event.event_id, "status": "queued"}


@router.get("/deliveries")
def list_deliveries(
    delivery_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_permissions(Permission.WEBHOOKS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    del principal
    query = db.query(WebhookDelivery, OutboxEvent).join(OutboxEvent, OutboxEvent.id == WebhookDelivery.outbox_event_id)
    if delivery_status:
        query = query.filter(WebhookDelivery.status == delivery_status)
    rows = query.order_by(WebhookDelivery.created_at.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": int(delivery.id),
                "event_id": event.event_id,
                "event_type": event.event_type,
                "endpoint_id": int(delivery.endpoint_id),
                "status": delivery.status,
                "attempt_count": delivery.attempt_count,
                "next_attempt_at": delivery.next_attempt_at,
                "last_http_status": delivery.last_http_status,
                "last_error_code": delivery.last_error_code,
                "delivered_at": delivery.delivered_at,
            }
            for delivery, event in rows
        ]
    }


@router.post("/deliveries/{delivery_id}/redeliver")
def redeliver(
    delivery_id: int,
    principal: Principal = Depends(require_permissions(Permission.WEBHOOKS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).with_for_update().first()
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    if delivery.status not in {"dead", "delivered"}:
        raise HTTPException(status_code=409, detail="only dead or delivered records can be redelivered")
    delivery.status = "pending"
    delivery.attempt_count = 0
    delivery.next_attempt_at = datetime.now(timezone.utc)
    delivery.lease_expires_at = None
    delivery.last_error_code = None
    security_audit_service.append(
        db,
        event_type="webhook.delivery.redelivered",
        outcome="success",
        actor_user_id=principal.user_id,
        actor_session_id=principal.session_id,
        target_type="webhook_delivery",
        target_id=str(delivery.id),
        details={},
    )
    db.commit()
    return {"id": int(delivery.id), "status": "pending"}
