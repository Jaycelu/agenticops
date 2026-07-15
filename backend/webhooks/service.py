from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from models.webhook import OutboxEvent, WebhookDelivery, WebhookEndpoint


class WebhookService:
    def enqueue(
        self,
        db: Session,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        endpoint_ids: set[int] | None = None,
    ) -> OutboxEvent:
        event = OutboxEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            payload_version=1,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=self._sanitize(payload),
        )
        db.add(event)
        db.flush()
        query = db.query(WebhookEndpoint).filter(WebhookEndpoint.enabled.is_(True))
        if endpoint_ids is not None:
            query = query.filter(WebhookEndpoint.id.in_(endpoint_ids))
        endpoints = query.all()
        for endpoint in endpoints:
            subscriptions = set(endpoint.event_types or [])
            if endpoint_ids is not None or "*" in subscriptions or event_type in subscriptions:
                db.add(
                    WebhookDelivery(
                        outbox_event_id=event.id,
                        endpoint_id=endpoint.id,
                        status="pending",
                    )
                )
        return event

    def _sanitize(self, payload: dict[str, Any]) -> dict[str, Any]:
        def clean(value: Any, key: str = "") -> Any:
            if any(item in key.lower() for item in ("password", "secret", "token", "credential", "private_key")):
                return "<redacted>"
            if isinstance(value, dict):
                return {str(k)[:120]: clean(v, str(k)) for k, v in list(value.items())[:200]}
            if isinstance(value, list):
                return [clean(item) for item in value[:200]]
            if isinstance(value, str):
                return value[:4096]
            if value is None or isinstance(value, (bool, int, float)):
                return value
            return str(value)[:4096]

        return clean(payload)


webhook_service = WebhookService()
