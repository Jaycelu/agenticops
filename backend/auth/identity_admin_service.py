from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from audit.service import security_audit_service
from auth.providers.common import encrypt_provider_secret
from auth.providers.registry import identity_provider_registry
from auth.rbac import Role
from auth.schemas import Principal
from models.auth import IdentityProvider, RoleBinding, UserAccount


PROVIDER_FIELDS: dict[str, dict[str, frozenset[str]]] = {
    "local": {"config": frozenset(), "secrets": frozenset()},
    "oidc": {
        "config": frozenset(
            {
                "metadata_url",
                "issuer",
                "client_id",
                "scopes",
                "username_claim",
                "groups_claim",
                "id_token_algorithms",
            }
        ),
        "secrets": frozenset({"client_secret"}),
    },
    "ldap": {
        "config": frozenset(
            {
                "url",
                "start_tls",
                "ca_certs_file",
                "bind_dn",
                "user_base_dn",
                "user_filter",
                "attributes",
                "username_attribute",
                "display_name_attribute",
                "email_attribute",
                "groups_attribute",
                "connect_timeout_seconds",
            }
        ),
        "secrets": frozenset({"bind_password"}),
    },
    "saml": {
        "config": frozenset(
            {
                "sp_entity_id",
                "sp_x509_cert",
                "idp_entity_id",
                "sso_url",
                "idp_x509_cert",
                "authn_requests_signed",
                "want_messages_signed",
                "want_assertions_encrypted",
                "username_attribute",
                "display_name_attribute",
                "email_attribute",
                "groups_attribute",
            }
        ),
        "secrets": frozenset({"sp_private_key"}),
    },
}


def _validate_mapping(mapping: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for group, raw_roles in mapping.items():
        if isinstance(raw_roles, str):
            roles = [raw_roles]
        elif isinstance(raw_roles, (list, tuple, set, frozenset)):
            roles = list(raw_roles)
        else:
            raise ValueError(f"roles for group {group!r} must be a string or list")
        normalized = sorted({Role(str(role)).value for role in roles})
        if normalized:
            result[str(group)[:512]] = normalized
    return result


class IdentityAdminService:
    def list_providers(self, db: Session) -> list[dict[str, Any]]:
        return [self.provider_view(row) for row in db.query(IdentityProvider).order_by(IdentityProvider.id).all()]

    def provider_view(self, provider: IdentityProvider) -> dict[str, Any]:
        return {
            "id": int(provider.id),
            "provider_key": provider.provider_key,
            "provider_type": provider.provider_type,
            "display_name": provider.display_name,
            "enabled": provider.enabled,
            "config": provider.config or {},
            "secret_status": {key: bool(value) for key, value in (provider.secrets_encrypted or {}).items()},
            "group_role_mapping": provider.group_role_mapping or {},
            "updated_at": provider.updated_at,
        }

    def upsert_provider(
        self,
        db: Session,
        *,
        provider_key: str,
        provider_type: str,
        display_name: str,
        enabled: bool,
        config: dict[str, Any],
        secrets: dict[str, str],
        clear_secrets: set[str],
        group_role_mapping: dict[str, Any],
        actor: Principal,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,79}", provider_key):
            raise ValueError("provider_key must contain 2-80 lowercase letters, numbers, '_' or '-'")
        spec = PROVIDER_FIELDS.get(provider_type)
        if spec is None or provider_type not in identity_provider_registry.list_types():
            raise ValueError(f"unsupported provider type: {provider_type}")
        unknown_config = set(config) - spec["config"]
        unknown_secrets = (set(secrets) | clear_secrets) - spec["secrets"]
        if unknown_config or unknown_secrets:
            raise ValueError(
                f"unsupported provider fields: config={sorted(unknown_config)}, secrets={sorted(unknown_secrets)}"
            )
        row = db.query(IdentityProvider).filter(IdentityProvider.provider_key == provider_key).first()
        created = row is None
        if row is None:
            row = IdentityProvider(
                provider_key=provider_key,
                provider_type=provider_type,
                display_name=display_name,
                enabled=False,
                config={},
                secrets_encrypted={},
                group_role_mapping={},
            )
            db.add(row)
            db.flush()
        elif row.provider_type != provider_type:
            raise ValueError("provider_type is immutable; create a new provider key")
        encrypted = dict(row.secrets_encrypted or {})
        for key in clear_secrets:
            encrypted.pop(key, None)
        for key, value in secrets.items():
            if value:
                encrypted[key] = encrypt_provider_secret(row, key, value)
        self._validate_enabled_provider(provider_type, enabled, config, encrypted)
        row.display_name = display_name.strip()
        row.enabled = bool(enabled)
        row.config = dict(config)
        row.secrets_encrypted = encrypted
        row.group_role_mapping = _validate_mapping(group_role_mapping)
        security_audit_service.append(
            db,
            event_type="auth.provider.created" if created else "auth.provider.updated",
            outcome="success",
            actor_user_id=actor.user_id,
            actor_session_id=actor.session_id,
            target_type="identity_provider",
            target_id=str(row.id),
            details={
                "provider_key": row.provider_key,
                "provider_type": row.provider_type,
                "enabled": row.enabled,
                "config_fields": sorted(row.config),
                "secret_fields": sorted(encrypted),
                "mapped_groups": sorted(row.group_role_mapping),
            },
        )
        db.commit()
        db.refresh(row)
        return self.provider_view(row)

    @staticmethod
    def _validate_enabled_provider(
        provider_type: str,
        enabled: bool,
        config: dict[str, Any],
        encrypted: dict[str, str],
    ) -> None:
        if not enabled or provider_type == "local":
            return
        required_config = {
            "oidc": {"metadata_url", "issuer", "client_id"},
            "ldap": {"url", "bind_dn", "user_base_dn"},
            "saml": {"sp_entity_id", "idp_entity_id", "sso_url", "idp_x509_cert"},
        }[provider_type]
        required_secrets = {"oidc": {"client_secret"}, "ldap": {"bind_password"}, "saml": set()}[
            provider_type
        ]
        missing = sorted(key for key in required_config if not config.get(key))
        missing.extend(sorted(key for key in required_secrets if not encrypted.get(key)))
        if missing:
            raise ValueError(f"cannot enable incomplete provider; missing: {', '.join(missing)}")

    def list_users(self, db: Session) -> list[dict[str, Any]]:
        users = db.query(UserAccount).order_by(func.lower(UserAccount.username)).all()
        bindings = db.query(RoleBinding).all()
        roles_by_user: dict[int, list[dict[str, Any]]] = {}
        for binding in bindings:
            roles_by_user.setdefault(int(binding.user_id), []).append(
                {"role": binding.role, "source": binding.source, "provider_id": binding.provider_id}
            )
        return [
            {
                "id": int(user.id),
                "username": user.username,
                "display_name": user.display_name,
                "email": user.email,
                "active": user.active,
                "is_emergency": user.is_emergency,
                "roles": roles_by_user.get(int(user.id), []),
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
            }
            for user in users
        ]

    def update_user(
        self,
        db: Session,
        *,
        user_id: int,
        active: bool,
        display_name: str,
        email: str | None,
        manual_roles: set[str],
        actor: Principal,
    ) -> dict[str, Any]:
        user = db.query(UserAccount).filter(UserAccount.id == user_id).with_for_update().first()
        if user is None:
            raise LookupError("user not found")
        desired = {Role(role).value for role in manual_roles}
        if user.id == actor.user_id and (not active or Role.ADMIN.value not in desired):
            raise ValueError("administrators cannot disable or remove their own admin role")
        existing = (
            db.query(RoleBinding)
            .filter(RoleBinding.user_id == user.id, RoleBinding.provider_id.is_(None))
            .all()
        )
        existing_by_role = {row.role: row for row in existing}
        for role, binding in existing_by_role.items():
            if role not in desired:
                db.delete(binding)
        for role in desired - set(existing_by_role):
            db.add(RoleBinding(user_id=user.id, role=role, source="manual", provider_id=None))
        user.active = active
        user.display_name = display_name.strip()
        user.email = email
        security_audit_service.append(
            db,
            event_type="auth.user.updated",
            outcome="success",
            actor_user_id=actor.user_id,
            actor_session_id=actor.session_id,
            target_type="user_account",
            target_id=str(user.id),
            details={"active": active, "manual_roles": sorted(desired)},
        )
        db.commit()
        return next(item for item in self.list_users(db) if item["id"] == user_id)


identity_admin_service = IdentityAdminService()
