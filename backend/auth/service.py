from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from audit.service import sanitize_audit_value, security_audit_service
from auth.crypto import decrypt_json, encrypt_json
from auth.providers.registry import identity_provider_registry
from auth.rbac import Role
from auth.schemas import AuthenticatedIdentity, Principal, SessionCredentials
from auth.session_service import auth_session_service, secret_digest
from config.settings import settings
from models.auth import (
    AuthLoginTransaction,
    ExternalIdentity,
    IdentityProvider,
    RoleBinding,
    UserAccount,
)


class AuthenticationFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class LoginResult:
    principal: Principal
    credentials: SessionCredentials


@dataclass(frozen=True)
class RedirectLoginStart:
    redirect_url: str
    state: str


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class AuthenticationService:
    def list_enabled_providers(self, db: Session) -> list[dict[str, str]]:
        providers = (
            db.query(IdentityProvider)
            .filter(IdentityProvider.enabled.is_(True))
            .order_by(IdentityProvider.display_name, IdentityProvider.id)
            .all()
        )
        return [
            {
                "key": provider.provider_key,
                "type": provider.provider_type,
                "display_name": provider.display_name,
                "flow": "credentials" if provider.provider_type in {"local", "ldap"} else "redirect",
            }
            for provider in providers
        ]

    def get_enabled_provider(self, db: Session, provider_key: str) -> IdentityProvider:
        provider = (
            db.query(IdentityProvider)
            .filter(
                IdentityProvider.provider_key == provider_key,
                IdentityProvider.enabled.is_(True),
            )
            .first()
        )
        if provider is None:
            raise AuthenticationFailed("identity provider is unavailable")
        identity_provider_registry.get(provider.provider_type)
        return provider

    async def authenticate_credentials(
        self,
        db: Session,
        *,
        provider_key: str,
        username: str,
        password: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> LoginResult:
        provider = self.get_enabled_provider(db, provider_key)
        if provider.provider_type not in {"local", "ldap"}:
            raise AuthenticationFailed("provider does not support password authentication")
        adapter = identity_provider_registry.get(provider.provider_type)
        identity = await adapter.authenticate_credentials(
            db,
            provider,
            username=username,
            password=password,
        )
        if identity is None:
            security_audit_service.append(
                db,
                event_type="auth.login",
                outcome="failed",
                target_type="identity_provider",
                target_id=provider.provider_key,
                source_ip=client_ip,
                details={"reason": "invalid_credentials", "username_digest": secret_digest(username.strip().lower())},
            )
            db.commit()
            raise AuthenticationFailed("invalid credentials")
        return self._finish_login(db, provider, identity, client_ip=client_ip, user_agent=user_agent)

    async def begin_redirect_login(
        self,
        db: Session,
        *,
        provider_key: str,
        callback_url: str,
    ) -> RedirectLoginStart:
        provider = self.get_enabled_provider(db, provider_key)
        if provider.provider_type not in {"oidc", "saml"}:
            raise AuthenticationFailed("provider does not support redirect authentication")
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        adapter = identity_provider_registry.get(provider.provider_type)
        start = await adapter.begin_login(
            provider,
            callback_url=callback_url,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
        )
        context = {"state": state, "nonce": nonce, **start.context}
        db.add(
            AuthLoginTransaction(
                id=secret_digest(state),
                provider_id=provider.id,
                flow_type=provider.provider_type,
                encrypted_context=encrypt_json(context, purpose="auth-login-transaction"),
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=settings.auth_login_transaction_ttl_minutes),
            )
        )
        db.commit()
        return RedirectLoginStart(start.redirect_url, state)

    async def complete_redirect_login(
        self,
        db: Session,
        *,
        provider_key: str,
        callback_url: str,
        request_data: dict[str, Any],
        client_ip: str | None,
        user_agent: str | None,
    ) -> LoginResult:
        provider = self.get_enabled_provider(db, provider_key)
        state = str(request_data.get("state") or request_data.get("RelayState") or "")
        if not state:
            raise AuthenticationFailed("missing login transaction state")
        transaction = (
            db.query(AuthLoginTransaction)
            .filter(
                AuthLoginTransaction.id == secret_digest(state),
                AuthLoginTransaction.provider_id == provider.id,
            )
            .with_for_update()
            .first()
        )
        now = datetime.now(timezone.utc)
        if (
            transaction is None
            or transaction.consumed_at is not None
            or _utc(transaction.expires_at) <= now
            or transaction.flow_type != provider.provider_type
        ):
            raise AuthenticationFailed("invalid, expired, or already consumed login transaction")
        context = decrypt_json(transaction.encrypted_context, purpose="auth-login-transaction")
        if not secrets.compare_digest(str(context.get("state") or ""), state):
            raise AuthenticationFailed("login transaction state mismatch")
        transaction.consumed_at = now
        db.commit()  # Persist one-time consumption before any remote token/assertion processing.

        adapter = identity_provider_registry.get(provider.provider_type)
        try:
            identity = await adapter.complete_login(
                provider,
                request_data=request_data,
                callback_url=callback_url,
                expected_state=state,
                expected_nonce=str(context.get("nonce") or ""),
                transaction_context={str(key): str(value) for key, value in context.items()},
            )
        except Exception as exc:
            security_audit_service.append(
                db,
                event_type="auth.login",
                outcome="failed",
                target_type="identity_provider",
                target_id=provider.provider_key,
                source_ip=client_ip,
                details={"reason": type(exc).__name__},
            )
            db.commit()
            raise AuthenticationFailed("external authentication failed") from exc
        return self._finish_login(db, provider, identity, client_ip=client_ip, user_agent=user_agent)

    def _finish_login(
        self,
        db: Session,
        provider: IdentityProvider,
        identity: AuthenticatedIdentity,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> LoginResult:
        user = self._resolve_user(db, provider, identity)
        if not user.active:
            raise AuthenticationFailed("user account is inactive")
        added_roles, removed_roles = self._sync_provider_roles(db, provider, user, identity.groups)
        if added_roles or removed_roles:
            security_audit_service.append(
                db,
                event_type="auth.roles.synced",
                outcome="success",
                actor_user_id=int(user.id),
                target_type="user_account",
                target_id=str(user.id),
                source_ip=client_ip,
                details={
                    "provider_key": provider.provider_key,
                    "added": sorted(added_roles),
                    "removed": sorted(removed_roles),
                },
            )
        user.last_login_at = datetime.now(timezone.utc)
        credentials = auth_session_service.create_session(
            db,
            user=user,
            provider_id=provider.id,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        db.flush()
        principal = auth_session_service.resolve_principal(db, credentials.session_token)
        if principal is None:
            raise AuthenticationFailed("failed to create authentication session")
        security_audit_service.append(
            db,
            event_type="auth.login",
            outcome="success",
            actor_user_id=int(user.id),
            actor_session_id=principal.session_id,
            target_type="identity_provider",
            target_id=provider.provider_key,
            source_ip=client_ip,
            details={"provider_type": provider.provider_type, "roles": sorted(principal.roles)},
        )
        db.commit()
        return LoginResult(principal, credentials)

    def _resolve_user(
        self,
        db: Session,
        provider: IdentityProvider,
        identity: AuthenticatedIdentity,
    ) -> UserAccount:
        if provider.provider_type == "local":
            user_id = int(identity.claims["user_id"])
            user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
            if user is None:
                raise AuthenticationFailed("local account no longer exists")
            return user

        external = (
            db.query(ExternalIdentity)
            .filter(
                ExternalIdentity.provider_id == provider.id,
                ExternalIdentity.subject == identity.subject,
            )
            .first()
        )
        if external is None:
            user = UserAccount(
                username=self._available_username(db, identity.username, identity.subject),
                display_name=identity.display_name[:160],
                email=identity.email,
                active=True,
                is_emergency=False,
            )
            db.add(user)
            db.flush()
            external = ExternalIdentity(user_id=user.id, provider_id=provider.id, subject=identity.subject)
            db.add(external)
        else:
            user = db.query(UserAccount).filter(UserAccount.id == external.user_id).first()
            if user is None:
                raise AuthenticationFailed("linked user account no longer exists")
        external.username_snapshot = identity.username[:160]
        external.email_snapshot = identity.email
        external.claims_snapshot = sanitize_audit_value(identity.claims)
        external.last_authenticated_at = datetime.now(timezone.utc)
        user.display_name = identity.display_name[:160]
        user.email = identity.email
        return user

    def _available_username(self, db: Session, requested: str, subject: str) -> str:
        base = requested.strip()[:120] or "external-user"
        exists = db.query(UserAccount.id).filter(func.lower(UserAccount.username) == base.lower()).first()
        if not exists:
            return base
        suffix = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:10]
        candidate = f"{base[:109]}-{suffix}"
        if db.query(UserAccount.id).filter(func.lower(UserAccount.username) == candidate.lower()).first():
            raise AuthenticationFailed("unable to allocate a unique external username")
        return candidate

    def _sync_provider_roles(
        self,
        db: Session,
        provider: IdentityProvider,
        user: UserAccount,
        groups: tuple[str, ...],
    ) -> tuple[set[str], set[str]]:
        mapping = provider.group_role_mapping or {}
        normalized_mapping = {str(key).casefold(): value for key, value in mapping.items()}
        desired: set[str] = set()
        for group in groups:
            raw_roles = normalized_mapping.get(group.casefold(), [])
            if isinstance(raw_roles, str):
                raw_roles = [raw_roles]
            for raw_role in raw_roles:
                try:
                    desired.add(Role(str(raw_role)).value)
                except ValueError:
                    continue
        existing = (
            db.query(RoleBinding)
            .filter(RoleBinding.user_id == user.id, RoleBinding.provider_id == provider.id)
            .all()
        )
        existing_by_role = {binding.role: binding for binding in existing}
        removed = set(existing_by_role) - desired
        added = desired - set(existing_by_role)
        for role, binding in existing_by_role.items():
            if role not in desired:
                db.delete(binding)
        for role in added:
            db.add(RoleBinding(user_id=user.id, role=role, source="provider", provider_id=provider.id))
        return added, removed


authentication_service = AuthenticationService()
