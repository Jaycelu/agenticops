from __future__ import annotations

import hashlib
import hmac
import socket

import pytest

from api.webhooks import endpoint_view
from models.webhook import WebhookEndpoint
from services.notification_executor import notification_executor
from webhooks.security import UnsafeWebhookURL, sign_payload, validate_webhook_url
from webhooks.service import webhook_service


pytestmark = pytest.mark.unit


def address_info(address: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


def test_webhook_url_rejects_private_loopback_metadata_and_credentials(monkeypatch) -> None:
    for address in ("127.0.0.1", "10.0.0.2", "169.254.169.254", "192.168.1.9"):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *args, value=address, **kwargs: address_info(value))
        with pytest.raises(UnsafeWebhookURL, match="non-public"):
            validate_webhook_url("https://hooks.example.test/events")

    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: address_info("8.8.8.8"))
    with pytest.raises(UnsafeWebhookURL, match="forbidden"):
        validate_webhook_url("https://user:password@hooks.example.test/events")
    with pytest.raises(UnsafeWebhookURL, match="HTTPS"):
        validate_webhook_url("http://hooks.example.test/events")


def test_webhook_delivery_url_is_pinned_after_dns_validation(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: address_info("8.8.8.8"))

    validated = validate_webhook_url("https://hooks.example.test:8443/events?tenant=ops")

    assert validated.hostname == "hooks.example.test"
    assert validated.pinned_url() == "https://8.8.8.8:8443/events?tenant=ops"


def test_webhook_hmac_covers_timestamp_event_id_and_exact_body() -> None:
    body = b'{"event":"approved"}'
    signature = sign_payload("shared-secret", 1234, "event-7", body)
    expected = hmac.new(b"shared-secret", b"1234.event-7." + body, hashlib.sha256).hexdigest()

    assert signature == f"v1={expected}"
    assert signature != sign_payload("shared-secret", 1234, "event-8", body)


def test_outbox_payload_redacts_secrets_and_bounds_strings() -> None:
    sanitized = webhook_service._sanitize(
        {"case_id": 7, "api_token": "must-not-leak", "nested": {"password": "hidden"}, "message": "x" * 5000}
    )

    assert sanitized["api_token"] == "<redacted>"
    assert sanitized["nested"]["password"] == "<redacted>"
    assert len(sanitized["message"]) == 4096


def test_endpoint_api_view_never_exposes_encrypted_secret() -> None:
    endpoint = WebhookEndpoint(
        id=4,
        name="SOC",
        url="https://hooks.example.test/events",
        enabled=True,
        event_types=["approval.requested"],
        secret_encrypted="ciphertext",
        secret_fingerprint="0123456789abcdef",
        timeout_seconds=10,
        max_attempts=8,
        created_by_user_id=1,
    )

    view = endpoint_view(endpoint)

    assert view["secret_fingerprint"] == "0123456789abcdef"
    assert "ciphertext" not in repr(view)


def test_legacy_notification_executor_cannot_send_agent_supplied_url() -> None:
    assert notification_executor.validate_config(
        {"webhook_url": "https://attacker.example", "message": "data"}
    ) is False
