from __future__ import annotations

import ssl
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from auth.providers.base import IdentityProviderAdapter
from auth.providers.common import (
    ProviderConfigurationError,
    provider_secret,
    required_config,
    safe_claims,
    string_list,
)
from auth.schemas import AuthenticatedIdentity
from models.auth import IdentityProvider


class LDAPIdentityProvider(IdentityProviderAdapter):
    """LDAP/Active Directory password authentication over verified TLS only."""

    provider_type = "ldap"

    async def authenticate_credentials(
        self,
        db: Session,
        provider: IdentityProvider,
        *,
        username: str,
        password: str,
    ) -> AuthenticatedIdentity | None:
        del db
        from anyio import to_thread

        return await to_thread.run_sync(self._authenticate_sync, provider, username, password)

    def _authenticate_sync(
        self,
        provider: IdentityProvider,
        username: str,
        password: str,
    ) -> AuthenticatedIdentity | None:
        from ldap3 import (
            ALL_ATTRIBUTES,
            AUTO_BIND_NO_TLS,
            AUTO_BIND_TLS_BEFORE_BIND,
            Connection,
            NONE,
            Server,
            Tls,
        )
        from ldap3.core.exceptions import LDAPInvalidCredentialsResult
        from ldap3.utils.conv import escape_filter_chars

        if not username.strip() or not password:
            return None
        uri = urlparse(required_config(provider, "url"))
        start_tls = bool((provider.config or {}).get("start_tls", False))
        if uri.scheme not in {"ldap", "ldaps"} or not uri.hostname:
            raise ProviderConfigurationError("LDAP url must use ldap:// or ldaps://")
        if uri.scheme == "ldap" and not start_tls:
            raise ProviderConfigurationError("plain LDAP is forbidden; enable StartTLS or use LDAPS")

        ca_file = str((provider.config or {}).get("ca_certs_file") or "").strip() or None
        tls = Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS_CLIENT, ca_certs_file=ca_file)
        server = Server(
            uri.hostname,
            port=uri.port or (636 if uri.scheme == "ldaps" else 389),
            use_ssl=uri.scheme == "ldaps",
            tls=tls,
            get_info=NONE,
            connect_timeout=int((provider.config or {}).get("connect_timeout_seconds") or 10),
        )
        auto_bind = AUTO_BIND_TLS_BEFORE_BIND if start_tls else AUTO_BIND_NO_TLS
        service = Connection(
            server,
            user=required_config(provider, "bind_dn"),
            password=provider_secret(provider, "bind_password"),
            auto_bind=auto_bind,
            raise_exceptions=True,
            receive_timeout=10,
        )
        try:
            filter_template = str((provider.config or {}).get("user_filter") or "(uid={username})")
            if filter_template.count("{username}") != 1:
                raise ProviderConfigurationError("LDAP user_filter must contain exactly one {username}")
            search_filter = filter_template.replace("{username}", escape_filter_chars(username.strip()))
            attributes = set(
                string_list(
                    (provider.config or {}).get("attributes"),
                    default=("uid", "cn", "mail", "memberOf"),
                )
            )
            attributes.update(
                {
                    str((provider.config or {}).get("username_attribute") or "uid"),
                    str((provider.config or {}).get("display_name_attribute") or "cn"),
                    str((provider.config or {}).get("email_attribute") or "mail"),
                    str((provider.config or {}).get("groups_attribute") or "memberOf"),
                }
            )
            found = service.search(
                search_base=required_config(provider, "user_base_dn"),
                search_filter=search_filter,
                attributes=list(attributes) or ALL_ATTRIBUTES,
                size_limit=2,
            )
            if not found or len(service.entries) != 1:
                return None
            entry = service.entries[0]
            user_dn = str(entry.entry_dn)
            values = entry.entry_attributes_as_dict
        finally:
            service.unbind()

        user_connection = None
        try:
            user_connection = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=auto_bind,
                raise_exceptions=True,
                receive_timeout=10,
            )
        except LDAPInvalidCredentialsResult:
            return None
        finally:
            if user_connection is not None:
                user_connection.unbind()

        def first(name: str) -> str | None:
            value = values.get(name)
            if isinstance(value, list):
                return str(value[0]) if value else None
            return str(value) if value is not None else None

        username_attr = str((provider.config or {}).get("username_attribute") or "uid")
        display_attr = str((provider.config or {}).get("display_name_attribute") or "cn")
        email_attr = str((provider.config or {}).get("email_attribute") or "mail")
        groups_attr = str((provider.config or {}).get("groups_attribute") or "memberOf")
        raw_groups = values.get(groups_attr) or []
        groups = string_list(raw_groups if isinstance(raw_groups, list) else [raw_groups])
        resolved_username = first(username_attr) or username.strip()
        return AuthenticatedIdentity(
            provider_key=provider.provider_key,
            subject=user_dn,
            username=resolved_username,
            display_name=first(display_attr) or resolved_username,
            email=first(email_attr),
            groups=groups,
            claims=safe_claims(
                {"dn": user_dn, username_attr: resolved_username, display_attr: first(display_attr), email_attr: first(email_attr), groups_attr: groups},
                ("dn", username_attr, display_attr, email_attr, groups_attr),
            ),
        )
