from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from auth.schemas import Principal, SessionCredentials
from config.settings import settings
from models.auth import AuthSession, RoleBinding, UserAccount


def secret_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def auth_secret_bytes() -> bytes:
    value = settings.app_secret_key.encode("utf-8")
    if len(value) < 32:
        raise RuntimeError("APP_SECRET_KEY must contain at least 32 bytes for authentication")
    return value


def privacy_digest(value: str | None) -> str | None:
    if not value:
        return None
    return hmac.new(auth_secret_bytes(), value.encode("utf-8"), hashlib.sha256).hexdigest()


class AuthSessionService:
    def create_session(
        self,
        db: Session,
        *,
        user: UserAccount,
        provider_id: int | None,
        client_ip: str | None,
        user_agent: str | None,
    ) -> SessionCredentials:
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.auth_session_ttl_hours)
        db.add(
            AuthSession(
                id=secret_digest(session_token),
                user_id=user.id,
                provider_id=provider_id,
                csrf_token_hash=secret_digest(csrf_token),
                client_ip_hash=privacy_digest(client_ip),
                user_agent_hash=privacy_digest(user_agent),
                expires_at=expires_at,
                last_seen_at=datetime.now(timezone.utc),
            )
        )
        db.flush()
        return SessionCredentials(session_token=session_token, csrf_token=csrf_token, expires_at=expires_at)

    def resolve_principal(self, db: Session, session_token: str) -> Principal | None:
        session_id = secret_digest(session_token)
        row = (
            db.query(AuthSession, UserAccount)
            .join(UserAccount, UserAccount.id == AuthSession.user_id)
            .filter(AuthSession.id == session_id)
            .first()
        )
        if row is None:
            return None
        auth_session, user = row
        now = datetime.now(timezone.utc)
        expires_at = auth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if auth_session.revoked_at is not None or expires_at <= now or not user.active:
            return None

        roles = frozenset(
            role
            for (role,) in db.query(RoleBinding.role).filter(RoleBinding.user_id == user.id).all()
        )
        from auth.rbac import permissions_for_roles

        return Principal(
            user_id=int(user.id),
            username=user.username,
            display_name=user.display_name,
            roles=roles,
            permissions=permissions_for_roles(roles),
            session_id=auth_session.id,
        )

    def validate_csrf(self, auth_session: AuthSession, csrf_token: str) -> bool:
        return hmac.compare_digest(auth_session.csrf_token_hash, secret_digest(csrf_token))

    def revoke_session(self, db: Session, session_id: str) -> bool:
        auth_session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
        if auth_session is None or auth_session.revoked_at is not None:
            return False
        auth_session.revoked_at = datetime.now(timezone.utc)
        db.flush()
        return True


auth_session_service = AuthSessionService()
