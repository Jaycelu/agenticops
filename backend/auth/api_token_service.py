from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from audit.service import security_audit_service
from auth.rbac import Permission
from auth.schemas import Principal
from auth.session_service import auth_secret_bytes
from models.auth import ApiToken, UserAccount


TOKEN_PREFIX = "agt_"
MACHINE_TOKEN_PERMISSIONS = frozenset({Permission.EVENTS_INGEST.value})


def api_token_digest(value: str) -> str:
    import hashlib

    return hmac.new(auth_secret_bytes(), value.encode("utf-8"), hashlib.sha256).hexdigest()


class ApiTokenService:
    def create(
        self,
        db: Session,
        *,
        name: str,
        permissions: set[str],
        created_by: Principal,
        expires_at: datetime | None,
    ) -> tuple[ApiToken, str]:
        unsupported = permissions - MACHINE_TOKEN_PERMISSIONS
        if unsupported or not permissions:
            raise ValueError(
                f"API tokens may only use machine permissions: {sorted(MACHINE_TOKEN_PERMISSIONS)}"
            )
        if expires_at is not None:
            expires_at = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError("API token expiry must be in the future")
        prefix = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)
        plaintext = f"{TOKEN_PREFIX}{prefix}.{secret}"
        row = ApiToken(
            name=name.strip(),
            token_prefix=prefix,
            secret_hash=api_token_digest(plaintext),
            permissions=sorted(permissions),
            active=True,
            expires_at=expires_at,
            created_by_user_id=created_by.user_id,
        )
        db.add(row)
        db.flush()
        security_audit_service.append(
            db,
            event_type="auth.api_token.created",
            outcome="success",
            actor_user_id=created_by.user_id,
            actor_session_id=created_by.session_id,
            target_type="api_token",
            target_id=str(row.id),
            details={"name": row.name, "permissions": row.permissions, "expires_at": expires_at},
        )
        db.commit()
        db.refresh(row)
        return row, plaintext

    def authenticate(self, db: Session, plaintext: str) -> Principal | None:
        if not plaintext.startswith(TOKEN_PREFIX) or "." not in plaintext:
            return None
        prefix = plaintext[len(TOKEN_PREFIX) :].split(".", 1)[0]
        if len(prefix) != 12:
            return None
        result = (
            db.query(ApiToken, UserAccount)
            .join(UserAccount, UserAccount.id == ApiToken.created_by_user_id)
            .filter(ApiToken.token_prefix == prefix)
            .first()
        )
        if result is None:
            return None
        token, owner = result
        now = datetime.now(timezone.utc)
        expires_at = token.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if (
            not token.active
            or token.revoked_at is not None
            or not owner.active
            or (expires_at is not None and expires_at <= now)
            or not hmac.compare_digest(token.secret_hash, api_token_digest(plaintext))
        ):
            return None
        permissions = frozenset(
            item for item in (token.permissions or []) if item in MACHINE_TOKEN_PERMISSIONS
        )
        token.last_used_at = now
        return Principal(
            user_id=int(owner.id),
            username=owner.username,
            display_name=owner.display_name,
            roles=frozenset(),
            permissions=permissions,
            session_id=None,
            auth_type="api_token",
            token_id=int(token.id),
        )

    def revoke(self, db: Session, token_id: int, *, actor: Principal) -> bool:
        token = db.query(ApiToken).filter(ApiToken.id == token_id).with_for_update().first()
        if token is None:
            return False
        if token.revoked_at is None:
            token.revoked_at = datetime.now(timezone.utc)
            token.active = False
            security_audit_service.append(
                db,
                event_type="auth.api_token.revoked",
                outcome="success",
                actor_user_id=actor.user_id,
                actor_session_id=actor.session_id,
                target_type="api_token",
                target_id=str(token.id),
                details={"name": token.name},
            )
            db.commit()
        return True


api_token_service = ApiTokenService()
