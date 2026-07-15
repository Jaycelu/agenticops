from __future__ import annotations

from typing import Any

from auth.crypto import decrypt_text, encrypt_text
from models.auth import IdentityProvider


class ProviderConfigurationError(ValueError):
    pass


class ProviderAuthenticationError(RuntimeError):
    pass


def required_config(provider: IdentityProvider, key: str) -> str:
    value = str((provider.config or {}).get(key) or "").strip()
    if not value:
        raise ProviderConfigurationError(f"provider configuration is missing: {key}")
    return value


def provider_secret(provider: IdentityProvider, key: str) -> str:
    encrypted = str((provider.secrets_encrypted or {}).get(key) or "")
    if not encrypted:
        raise ProviderConfigurationError(f"provider secret is missing: {key}")
    return decrypt_text(encrypted, purpose=f"identity-provider:{provider.id}:{key}")


def encrypt_provider_secret(provider: IdentityProvider, key: str, value: str) -> str:
    if provider.id is None:
        raise ProviderConfigurationError("provider must be persisted before encrypting secrets")
    return encrypt_text(value, purpose=f"identity-provider:{provider.id}:{key}")


def string_list(value: Any, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, str):
        return tuple(item for item in value.split() if item)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    raise ProviderConfigurationError("expected a string or list of strings")


def safe_claims(claims: dict[str, Any], allowed: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in allowed:
        value = claims.get(key)
        if value is None or isinstance(value, (bool, int, float)):
            result[key] = value
        elif isinstance(value, str):
            result[key] = value[:1024]
        elif isinstance(value, (list, tuple)):
            result[key] = [str(item)[:512] for item in list(value)[:100]]
    return result
