from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import or_

from config.settings import settings
from database import SessionLocal
from models.webhook import OutboxEvent, WebhookDelivery, WebhookEndpoint
from webhooks.security import decrypt_endpoint_secret, sign_payload, validate_webhook_url


logger = logging.getLogger(__name__)


class WebhookWorker:
    def run_once(self) -> bool:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            delivery = (
                db.query(WebhookDelivery)
                .filter(
                    or_(
                        (WebhookDelivery.status.in_(["pending", "retry"]))
                        & (WebhookDelivery.next_attempt_at <= now),
                        (WebhookDelivery.status == "delivering")
                        & (WebhookDelivery.lease_expires_at < now),
                    )
                )
                .order_by(WebhookDelivery.next_attempt_at, WebhookDelivery.id)
                .with_for_update(skip_locked=True)
                .first()
            )
            if delivery is None:
                db.rollback()
                return False
            delivery.status = "delivering"
            delivery.attempt_count += 1
            delivery.lease_expires_at = now + timedelta(seconds=settings.webhook_lease_seconds)
            delivery_id = int(delivery.id)
            db.commit()
        finally:
            db.close()

        self._deliver(delivery_id)
        return True

    def _deliver(self, delivery_id: int) -> None:
        db = SessionLocal()
        try:
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
            if delivery is None or delivery.status != "delivering":
                return
            endpoint = db.query(WebhookEndpoint).filter(WebhookEndpoint.id == delivery.endpoint_id).first()
            event = db.query(OutboxEvent).filter(OutboxEvent.id == delivery.outbox_event_id).first()
            if endpoint is None or event is None or not endpoint.enabled:
                self._fail(db, delivery, endpoint, "endpoint_unavailable", retryable=False)
                return
            envelope = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "payload_version": event.payload_version,
                "aggregate": {"type": event.aggregate_type, "id": event.aggregate_id},
                "created_at": event.created_at.isoformat(),
                "data": event.payload,
            }
            body = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            timestamp = int(time.time())
            validated = validate_webhook_url(endpoint.url, allow_http=settings.webhook_allow_http)
            secret = decrypt_endpoint_secret(endpoint)
            parsed = httpx.URL(validated.url)
            host_header = parsed.host
            if parsed.port:
                host_header = f"{host_header}:{parsed.port}"
            headers = {
                "Content-Type": "application/json",
                "Host": host_header,
                "X-AgenticOps-Event-Id": event.event_id,
                "X-AgenticOps-Timestamp": str(timestamp),
                "X-AgenticOps-Signature": sign_payload(secret, timestamp, event.event_id, body),
            }
            with httpx.Client(timeout=endpoint.timeout_seconds, follow_redirects=False, trust_env=False) as client:
                request = client.build_request("POST", validated.pinned_url(), headers=headers, content=body)
                request.extensions["sni_hostname"] = validated.hostname
                response = client.send(request)
            delivery.last_http_status = response.status_code
            delivery.response_digest = hashlib.sha256(response.content[:65536]).hexdigest()
            if 200 <= response.status_code < 300:
                delivery.status = "delivered"
                delivery.delivered_at = datetime.now(timezone.utc)
                delivery.lease_expires_at = None
                delivery.last_error_code = None
                db.commit()
                return
            retryable = response.status_code in {408, 425, 429} or response.status_code >= 500
            self._fail(db, delivery, endpoint, f"http_{response.status_code}", retryable=retryable)
        except (httpx.HTTPError, OSError, ValueError) as exc:
            db.rollback()
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).with_for_update().first()
            endpoint = (
                db.query(WebhookEndpoint).filter(WebhookEndpoint.id == delivery.endpoint_id).first()
                if delivery
                else None
            )
            if delivery:
                self._fail(db, delivery, endpoint, type(exc).__name__, retryable=True)
        finally:
            db.close()

    @staticmethod
    def _fail(
        db,
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint | None,
        error_code: str,
        *,
        retryable: bool,
    ) -> None:
        max_attempts = endpoint.max_attempts if endpoint else 1
        exhausted = delivery.attempt_count >= max_attempts
        delivery.status = "retry" if retryable and not exhausted else "dead"
        delivery.last_error_code = error_code[:120]
        delivery.lease_expires_at = None
        if delivery.status == "retry":
            delay = min(3600, 5 * (2 ** max(0, delivery.attempt_count - 1)))
            delivery.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        db.commit()
        if delivery.status == "dead":
            logger.error("webhook delivery moved to dead letter delivery_id=%s error_code=%s", delivery.id, error_code)


webhook_worker = WebhookWorker()
