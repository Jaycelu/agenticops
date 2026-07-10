from __future__ import annotations

from abc import ABC
from typing import Any

from sqlalchemy.orm import Session

from auth.schemas import AuthenticatedIdentity
from models.auth import IdentityProvider


class ProviderFlowNotSupported(RuntimeError):
    pass


class IdentityProviderAdapter(ABC):
    provider_type: str

    async def authenticate_credentials(
        self,
        db: Session,
        provider: IdentityProvider,
        *,
        username: str,
        password: str,
    ) -> AuthenticatedIdentity | None:
        raise ProviderFlowNotSupported(f"{self.provider_type} does not support password authentication")

    async def begin_login(
        self,
        provider: IdentityProvider,
        *,
        callback_url: str,
        state: str,
        nonce: str,
    ) -> str:
        raise ProviderFlowNotSupported(f"{self.provider_type} does not support redirect login")

    async def complete_login(
        self,
        provider: IdentityProvider,
        *,
        request_data: dict[str, Any],
        callback_url: str,
        expected_state: str,
        expected_nonce: str,
    ) -> AuthenticatedIdentity:
        raise ProviderFlowNotSupported(f"{self.provider_type} does not support redirect login")
