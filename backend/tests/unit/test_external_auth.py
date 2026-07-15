from __future__ import annotations

from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlparse

import pytest

from auth.crypto import decrypt_json, encrypt_json
from auth.providers.common import ProviderConfigurationError
from auth.providers.oidc import OIDCIdentityProvider, _unverified_header, validate_id_token
from auth.providers.saml import SAMLIdentityProvider
from models.auth import IdentityProvider


pytestmark = pytest.mark.unit


def provider(provider_type: str, config: dict, *, provider_id: int = 7) -> IdentityProvider:
    return IdentityProvider(
        id=provider_id,
        provider_key=f"test-{provider_type}",
        provider_type=provider_type,
        display_name=f"Test {provider_type}",
        enabled=True,
        config=config,
        secrets_encrypted={},
        group_role_mapping={},
    )


def test_runtime_uses_one_database_url_only() -> None:
    root = Path(__file__).resolve().parents[3]
    settings_source = (root / "backend/config/settings.py").read_text(encoding="utf-8")
    database_source = (root / "backend/database.py").read_text(encoding="utf-8")
    compose_source = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "automation_database_url" not in settings_source
    assert "automation_database_url" not in database_source
    assert "AUTOMATION_DATABASE_URL" not in compose_source
    assert len(re.findall(r"^  postgres:$", compose_source, flags=re.MULTILINE)) == 1


def test_login_transaction_context_is_encrypted_and_purpose_bound() -> None:
    encrypted = encrypt_json({"state": "not-visible", "nonce": "secret"}, purpose="auth-login-transaction")

    assert "not-visible" not in encrypted
    assert decrypt_json(encrypted, purpose="auth-login-transaction") == {
        "state": "not-visible",
        "nonce": "secret",
    }
    with pytest.raises(Exception):
        decrypt_json(encrypted, purpose="different-purpose")


@pytest.mark.asyncio
async def test_oidc_login_start_contains_state_nonce_and_pkce(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OIDCIdentityProvider()
    item = provider(
        "oidc",
        {
            "metadata_url": "https://idp.example/.well-known/openid-configuration",
            "issuer": "https://idp.example",
            "client_id": "agenticops",
        },
    )

    async def metadata(_provider):
        return {"authorization_endpoint": "https://idp.example/authorize"}

    monkeypatch.setattr(adapter, "_metadata", metadata)
    start = await adapter.begin_login(
        item,
        callback_url="https://ops.example/api/auth/callback/test-oidc",
        state="expected-state",
        nonce="expected-nonce",
        code_verifier="v" * 64,
    )
    query = parse_qs(urlparse(start.redirect_url).query)

    assert query["state"] == ["expected-state"]
    assert query["nonce"] == ["expected-nonce"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0] != "v" * 64


def test_oidc_rejects_malformed_token_header() -> None:
    with pytest.raises(Exception, match="malformed"):
        _unverified_header("not-a-jwt")


def test_oidc_id_token_validation_enforces_signature_issuer_audience_and_nonce() -> None:
    from authlib.jose import JsonWebKey, jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    key = JsonWebKey.import_key(private_pem, {"kid": "test-key"})
    now = int(time.time())
    token = jwt.encode(
        {"alg": "RS256", "kid": "test-key"},
        {
            "iss": "https://idp.example",
            "aud": "agenticops",
            "sub": "stable-user-id",
            "iat": now,
            "exp": now + 300,
            "nonce": "expected-nonce",
        },
        key,
    ).decode("ascii")
    jwks = {"keys": [key.as_dict(is_private=False)]}

    claims = validate_id_token(
        token,
        jwks=jwks,
        issuer="https://idp.example",
        client_id="agenticops",
        expected_nonce="expected-nonce",
        access_token=None,
        allowed_algorithms=("RS256",),
    )
    assert claims["sub"] == "stable-user-id"

    with pytest.raises(Exception):
        validate_id_token(
            token,
            jwks=jwks,
            issuer="https://idp.example",
            client_id="agenticops",
            expected_nonce="wrong-nonce",
            access_token=None,
            allowed_algorithms=("RS256",),
        )


def test_saml_settings_require_signed_assertions_and_response_correlation() -> None:
    adapter = SAMLIdentityProvider()
    item = provider(
        "saml",
        {
            "sp_entity_id": "https://ops.example/saml/metadata",
            "idp_entity_id": "https://idp.example/metadata",
            "sso_url": "https://idp.example/sso",
            "idp_x509_cert": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
        },
    )
    saml_settings = adapter._settings(item, "https://ops.example/api/auth/callback/test-saml")

    assert saml_settings["strict"] is True
    assert saml_settings["security"]["wantAssertionsSigned"] is True
    assert saml_settings["security"]["rejectUnsolicitedResponsesWithInResponseTo"] is True


def test_saml_rejects_cleartext_sso_url() -> None:
    adapter = SAMLIdentityProvider()
    item = provider(
        "saml",
        {
            "sp_entity_id": "https://ops.example/saml/metadata",
            "idp_entity_id": "https://idp.example/metadata",
            "sso_url": "http://idp.example/sso",
            "idp_x509_cert": "certificate",
        },
    )

    with pytest.raises(ProviderConfigurationError, match="HTTPS"):
        adapter._settings(item, "https://ops.example/api/auth/callback/test-saml")
