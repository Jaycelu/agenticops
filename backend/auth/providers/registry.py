from __future__ import annotations

from auth.providers.base import IdentityProviderAdapter
from auth.providers.local import LocalIdentityProvider
from auth.providers.ldap import LDAPIdentityProvider
from auth.providers.oidc import OIDCIdentityProvider
from auth.providers.saml import SAMLIdentityProvider


class IdentityProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, IdentityProviderAdapter] = {}

    def register(self, adapter: IdentityProviderAdapter) -> None:
        if adapter.provider_type in self._adapters:
            raise ValueError(f"identity provider adapter already registered: {adapter.provider_type}")
        self._adapters[adapter.provider_type] = adapter

    def get(self, provider_type: str) -> IdentityProviderAdapter:
        adapter = self._adapters.get(provider_type)
        if adapter is None:
            raise LookupError(f"identity provider adapter is not registered: {provider_type}")
        return adapter

    def list_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


identity_provider_registry = IdentityProviderRegistry()
identity_provider_registry.register(LocalIdentityProvider())
identity_provider_registry.register(LDAPIdentityProvider())
identity_provider_registry.register(OIDCIdentityProvider())
identity_provider_registry.register(SAMLIdentityProvider())
