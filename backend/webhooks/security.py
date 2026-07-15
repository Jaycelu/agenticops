from __future__ import annotations

import hashlib
import hmac
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from auth.crypto import decrypt_text, encrypt_text
from models.webhook import WebhookEndpoint


class UnsafeWebhookURL(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedWebhookURL:
    url: str
    hostname: str
    addresses: tuple[str, ...]

    def pinned_url(self) -> str:
        parsed = urlsplit(self.url)
        address = ipaddress.ip_address(self.addresses[0])
        host = f"[{address}]" if address.version == 6 else str(address)
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, ""))


def validate_webhook_url(url: str, *, allow_http: bool = False) -> ValidatedWebhookURL:
    parsed = urlsplit(url.strip())
    allowed_schemes = {"https", "http"} if allow_http else {"https"}
    if parsed.scheme not in allowed_schemes:
        raise UnsafeWebhookURL("webhook URL must use HTTPS")
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise UnsafeWebhookURL("webhook URL contains forbidden components")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeWebhookURL("webhook hostname cannot be resolved") from exc
    addresses = tuple(sorted({item[4][0] for item in infos}))
    if not addresses:
        raise UnsafeWebhookURL("webhook hostname has no addresses")
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        if not address.is_global:
            raise UnsafeWebhookURL("webhook target resolves to a non-public address")
    return ValidatedWebhookURL(url=parsed.geturl(), hostname=parsed.hostname, addresses=addresses)


def encrypt_endpoint_secret(endpoint: WebhookEndpoint, secret: str) -> str:
    if endpoint.id is None:
        raise ValueError("endpoint must be persisted before secret encryption")
    return encrypt_text(secret, purpose=f"webhook-endpoint:{endpoint.id}")


def decrypt_endpoint_secret(endpoint: WebhookEndpoint) -> str:
    return decrypt_text(endpoint.secret_encrypted, purpose=f"webhook-endpoint:{endpoint.id}")


def secret_fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


def sign_payload(secret: str, timestamp: int, event_id: str, body: bytes) -> str:
    signed = str(timestamp).encode("ascii") + b"." + event_id.encode("ascii") + b"." + body
    return "v1=" + hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
