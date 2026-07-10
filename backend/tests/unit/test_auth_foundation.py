from __future__ import annotations

import pytest

from audit.service import calculate_event_hash, canonical_json, sanitize_audit_value
from auth.providers.local import LocalPasswordService
from auth.providers.registry import identity_provider_registry
from auth.rbac import Permission, Role, permissions_for_roles
from auth.session_service import auth_secret_bytes, privacy_digest, secret_digest


pytestmark = pytest.mark.unit


def test_local_passwords_use_argon2id_and_verify() -> None:
    service = LocalPasswordService()
    encoded = service.hash_password("correct-horse-battery-staple")

    assert encoded.startswith("$argon2id$")
    assert service.verify_password(encoded, "correct-horse-battery-staple")
    assert not service.verify_password(encoded, "wrong-password")
    assert not service.verify_password(None, "correct-horse-battery-staple")


def test_local_password_policy_rejects_short_or_padded_values() -> None:
    service = LocalPasswordService()

    with pytest.raises(ValueError, match="at least"):
        service.hash_password("short")
    with pytest.raises(ValueError, match="whitespace"):
        service.hash_password(" padded-password-value ")


def test_provider_registry_fails_closed_for_unknown_type() -> None:
    assert identity_provider_registry.list_types() == ("local",)
    with pytest.raises(LookupError):
        identity_provider_registry.get("unknown")


def test_rbac_combines_roles_without_accepting_unknown_roles() -> None:
    permissions = permissions_for_roles({Role.OPERATOR.value, Role.APPROVER.value, "made-up"})

    assert Permission.CASES_READ.value in permissions
    assert Permission.PROBES_RUN.value in permissions
    assert Permission.APPROVALS_DECIDE.value in permissions
    assert Permission.EXECUTIONS_RUN.value not in permissions


def test_admin_has_every_declared_permission() -> None:
    assert permissions_for_roles({Role.ADMIN.value}) == frozenset(item.value for item in Permission)


def test_session_and_privacy_digests_are_deterministic_and_separate() -> None:
    assert len(auth_secret_bytes()) >= 32
    assert secret_digest("session-token") == secret_digest("session-token")
    assert secret_digest("session-token") != secret_digest("other-token")
    assert privacy_digest("192.0.2.10") == privacy_digest("192.0.2.10")
    assert privacy_digest("192.0.2.10") != secret_digest("192.0.2.10")
    assert privacy_digest(None) is None


def test_audit_hash_chain_is_canonical_and_tamper_evident() -> None:
    first_payload = {"event_type": "auth.login", "details": {"b": 2, "a": 1}}
    same_payload_different_order = {"details": {"a": 1, "b": 2}, "event_type": "auth.login"}
    first_hash = calculate_event_hash(None, first_payload)

    assert canonical_json(first_payload) == canonical_json(same_payload_different_order)
    assert first_hash == calculate_event_hash(None, same_payload_different_order)
    assert calculate_event_hash(first_hash, {"outcome": "success"}) != calculate_event_hash(
        first_hash,
        {"outcome": "failed"},
    )


def test_audit_details_redact_secrets_and_bound_payload_size() -> None:
    sanitized = sanitize_audit_value(
        {
            "username": "operator",
            "password": "must-not-leak",
            "nested": {"Authorization": "Bearer must-not-leak"},
            "message": "x" * 5000,
        }
    )

    assert sanitized["username"] == "operator"
    assert sanitized["password"] == "<redacted>"
    assert sanitized["nested"]["Authorization"] == "<redacted>"
    assert len(sanitized["message"]) == 4096
