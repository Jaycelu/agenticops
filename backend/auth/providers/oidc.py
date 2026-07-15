from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urlparse

import httpx

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


def _https_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ProviderConfigurationError(f"{label} must be an absolute HTTPS URL")
    return value


def _unverified_header(token: str) -> dict[str, Any]:
    try:
        encoded = token.split(".", 1)[0]
        encoded += "=" * (-len(encoded) % 4)
        value = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProviderAuthenticationError("OIDC id_token header is malformed") from exc
    if not isinstance(value, dict):
        raise ProviderAuthenticationError("OIDC id_token header is malformed")
    return value


def validate_id_token(
    id_token: str,
    *,
    jwks: dict[str, Any],
    issuer: str,
    client_id: str,
    expected_nonce: str,
    access_token: str | None,
    allowed_algorithms: tuple[str, ...],
) -> dict[str, Any]:
    from authlib.jose import JsonWebKey, jwt
    from authlib.oidc.core import CodeIDToken

    header = _unverified_header(id_token)
    algorithm = str(header.get("alg") or "")
    if algorithm not in allowed_algorithms or algorithm.startswith("HS") or algorithm == "none":
        raise ProviderAuthenticationError("OIDC id_token uses a disallowed signing algorithm")
    key_set = JsonWebKey.import_key_set(jwks)
    claims = jwt.decode(
        id_token,
        key_set,
        claims_cls=CodeIDToken,
        claims_options={
            "iss": {"essential": True, "value": issuer},
            "aud": {"essential": True, "value": client_id},
            "sub": {"essential": True},
        },
        claims_params={
            "nonce": expected_nonce,
            "access_token": access_token,
            "client_id": client_id,
        },
    )
    claims.validate(leeway=60)
    return dict(claims)


class OIDCIdentityProvider(IdentityProviderAdapter):
    provider_type = "oidc"

    async def _metadata(self, provider: IdentityProvider) -> dict[str, Any]:
        metadata_url = _https_url(required_config(provider, "metadata_url"), "metadata_url")
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(metadata_url, headers={"Accept": "application/json"})
            response.raise_for_status()
            metadata = response.json()
        issuer = _https_url(required_config(provider, "issuer"), "issuer")
        if metadata.get("issuer") != issuer:
            raise ProviderConfigurationError("OIDC discovery issuer does not match configured issuer")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            _https_url(str(metadata.get(key) or ""), key)
        return metadata

    async def begin_login(
        self,
        provider: IdentityProvider,
        *,
        callback_url: str,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> LoginStart:
        from authlib.integrations.httpx_client import AsyncOAuth2Client

        metadata = await self._metadata(provider)
        client = AsyncOAuth2Client(
            client_id=required_config(provider, "client_id"),
            scope=" ".join(string_list((provider.config or {}).get("scopes"), default=("openid", "profile", "email"))),
            code_challenge_method="S256",
        )
        url, _ = client.create_authorization_url(
            metadata["authorization_endpoint"],
            redirect_uri=callback_url,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
        )
        await client.aclose()
        return LoginStart(url, {"nonce": nonce, "code_verifier": code_verifier})

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
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        if request_data.get("state") != expected_state or not request_data.get("code"):
            raise ProviderAuthenticationError("invalid OIDC callback state or authorization code")
        metadata = await self._metadata(provider)
        client_id = required_config(provider, "client_id")
        client = AsyncOAuth2Client(client_id=client_id, client_secret=provider_secret(provider, "client_secret"))
        try:
            token = await client.fetch_token(
                metadata["token_endpoint"],
                code=str(request_data["code"]),
                redirect_uri=callback_url,
                code_verifier=transaction_context["code_verifier"],
            )
        finally:
            await client.aclose()
        id_token = str(token.get("id_token") or "")
        if not id_token:
            raise ProviderAuthenticationError("OIDC token response did not contain id_token")

        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
            jwks_response = await http.get(metadata["jwks_uri"], headers={"Accept": "application/json"})
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
        allowed_algorithms = string_list((provider.config or {}).get("id_token_algorithms"), default=("RS256",))
        raw = validate_id_token(
            id_token,
            jwks=jwks,
            issuer=required_config(provider, "issuer"),
            client_id=client_id,
            expected_nonce=expected_nonce,
            access_token=token.get("access_token"),
            allowed_algorithms=allowed_algorithms,
        )
        username_claim = str((provider.config or {}).get("username_claim") or "preferred_username")
        groups_claim = str((provider.config or {}).get("groups_claim") or "groups")
        subject = str(raw.get("sub") or "")
        username = str(raw.get(username_claim) or raw.get("email") or subject)
        groups = string_list(raw.get(groups_claim))
        return AuthenticatedIdentity(
            provider_key=provider.provider_key,
            subject=subject,
            username=username,
            display_name=str(raw.get("name") or username),
            email=str(raw.get("email")) if raw.get("email") else None,
            groups=groups,
            claims=safe_claims(raw, ("sub", username_claim, "name", "email", groups_claim, "iss", "aud")),
        )
