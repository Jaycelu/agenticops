from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuthenticatedIdentity:
    provider_key: str
    subject: str
    username: str
    display_name: str
    email: str | None = None
    groups: tuple[str, ...] = ()
    claims: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Principal:
    user_id: int
    username: str
    display_name: str
    roles: frozenset[str]
    permissions: frozenset[str]
    session_id: str


@dataclass(frozen=True)
class SessionCredentials:
    session_token: str
    csrf_token: str
    expires_at: datetime
