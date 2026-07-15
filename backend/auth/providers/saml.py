from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from auth.providers.base import IdentityProviderAdapter
from auth.providers.common import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    provider_secret,
    required_config,
    safe_claims,
    string_list,
)
from auth.schemas import AuthenticatedIdentity, LoginStart
from models.auth import IdentityProvider


def _request_environment(url: str, *, post_data: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ProviderConfigurationError("SAML callback URL must be an absolute HTTPS URL")
    return {
        "https": "on",
        "http_host": parsed.netloc,
        "server_port": str(parsed.port or 443),
        "script_name": parsed.path,
        "get_data": {},
        "post_data": post_data or {},
    }


class SAMLIdentityProvider(IdentityProviderAdapter):
    provider_type = "saml"

    def _settings(self, provider: IdentityProvider, callback_url: str) -> dict[str, Any]:
        config = provider.config or {}
        signed_requests = bool(config.get("authn_requests_signed", False))
        sso_url = required_config(provider, "sso_url")
        if urlparse(sso_url).scheme != "https":
            raise ProviderConfigurationError("SAML SSO URL must use HTTPS")
        sp: dict[str, Any] = {
            "entityId": required_config(provider, "sp_entity_id"),
            "assertionConsumerService": {
                "url": callback_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "x509cert": str(config.get("sp_x509_cert") or ""),
            "privateKey": provider_secret(provider, "sp_private_key") if signed_requests else "",
        }
        return {
            "strict": True,
            "debug": False,
            "sp": sp,
            "idp": {
                "entityId": required_config(provider, "idp_entity_id"),
                "singleSignOnService": {
                    "url": sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": required_config(provider, "idp_x509_cert"),
            },
            "security": {
                "authnRequestsSigned": signed_requests,
                "wantMessagesSigned": bool(config.get("want_messages_signed", False)),
                "wantAssertionsSigned": True,
                "wantAssertionsEncrypted": bool(config.get("want_assertions_encrypted", False)),
                "wantNameId": True,
                "rejectUnsolicitedResponsesWithInResponseTo": True,
                "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
                "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
            },
        }

    async def begin_login(
        self,
        provider: IdentityProvider,
        *,
        callback_url: str,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> LoginStart:
        del nonce, code_verifier
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        auth = OneLogin_Saml2_Auth(_request_environment(callback_url), self._settings(provider, callback_url))
        redirect_url = auth.login(return_to=state)
        request_id = str(auth.get_last_request_id() or "")
        if not request_id:
            raise ProviderAuthenticationError("SAML toolkit did not produce an AuthnRequest ID")
        return LoginStart(redirect_url, {"request_id": request_id})

    async def complete_login(
        self,
        provider: IdentityProvider,
        *,
        request_data: dict[str, Any],
        callback_url: str,
        expected_state: str,
        expected_nonce: str,
        transaction_context: dict[str, str],
    ) -> AuthenticatedIdentity:
        del expected_nonce
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        if request_data.get("RelayState") != expected_state:
            raise ProviderAuthenticationError("invalid SAML RelayState")
        auth = OneLogin_Saml2_Auth(
            _request_environment(callback_url, post_data=request_data),
            self._settings(provider, callback_url),
        )
        auth.process_response(request_id=transaction_context.get("request_id"))
        errors = auth.get_errors()
        if errors or not auth.is_authenticated():
            reason = auth.get_last_error_reason() or ",".join(errors) or "authentication failed"
            raise ProviderAuthenticationError(f"invalid SAML response: {reason}")
        subject = str(auth.get_nameid() or "")
        if not subject:
            raise ProviderAuthenticationError("SAML response has no persistent NameID")
        if "transient" in str(auth.get_nameid_format() or "").lower():
            raise ProviderAuthenticationError("transient SAML NameID cannot be used for account linking")
        attributes = auth.get_attributes() or {}

        def first(name: str) -> str | None:
            values = attributes.get(name) or []
            return str(values[0]) if values else None

        config = provider.config or {}
        username_attr = str(config.get("username_attribute") or "username")
        display_attr = str(config.get("display_name_attribute") or "displayName")
        email_attr = str(config.get("email_attribute") or "email")
        groups_attr = str(config.get("groups_attribute") or "groups")
        username = first(username_attr) or first(email_attr) or subject
        groups = string_list(attributes.get(groups_attr) or [])
        claims = {key: attributes.get(key) for key in (username_attr, display_attr, email_attr, groups_attr)}
        claims["name_id"] = subject
        return AuthenticatedIdentity(
            provider_key=provider.provider_key,
            subject=subject,
            username=username,
            display_name=first(display_attr) or username,
            email=first(email_attr),
            groups=groups,
            claims=safe_claims(claims, ("name_id", username_attr, display_attr, email_attr, groups_attr)),
        )
