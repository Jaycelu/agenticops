from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.identity_admin import ProviderUpsertRequest, UserUpdateRequest
from auth.identity_admin_service import IdentityAdminService, _validate_mapping
from auth.providers.common import encrypt_provider_secret, provider_secret
from models.auth import IdentityProvider


pytestmark = pytest.mark.unit


def provider(provider_type: str = "oidc") -> IdentityProvider:
    return IdentityProvider(
        id=42,
        provider_key=f"corp-{provider_type}",
        provider_type=provider_type,
        display_name="Corporate identity",
        enabled=False,
        config={},
        secrets_encrypted={},
        group_role_mapping={},
    )


def test_provider_secret_is_encrypted_and_never_exposed_by_admin_view() -> None:
    item = provider()
    item.secrets_encrypted = {"client_secret": encrypt_provider_secret(item, "client_secret", "top-secret")}

    view = IdentityAdminService().provider_view(item)

    assert provider_secret(item, "client_secret") == "top-secret"
    assert view["secret_status"] == {"client_secret": True}
    assert "top-secret" not in repr(view)
    assert item.secrets_encrypted["client_secret"] not in repr(view)


def test_group_mapping_rejects_non_collection_roles_and_unknown_roles() -> None:
    assert _validate_mapping({"network-ops": ["operator", "approver"]}) == {
        "network-ops": ["approver", "operator"]
    }
    with pytest.raises(ValueError, match="must be a string or list"):
        _validate_mapping({"network-ops": 7})
    with pytest.raises(ValueError):
        _validate_mapping({"network-ops": ["root"]})


def test_enabled_external_provider_requires_complete_configuration() -> None:
    validate = IdentityAdminService._validate_enabled_provider

    with pytest.raises(ValueError, match="client_secret"):
        validate(
            "oidc",
            True,
            {
                "metadata_url": "https://idp/.well-known/openid-configuration",
                "issuer": "https://idp",
                "client_id": "ops",
            },
            {},
        )
    validate(
        "oidc",
        True,
        {
            "metadata_url": "https://idp/.well-known/openid-configuration",
            "issuer": "https://idp",
            "client_id": "ops",
        },
        {"client_secret": "encrypted"},
    )


def test_identity_admin_requests_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProviderUpsertRequest.model_validate(
            {"provider_type": "local", "display_name": "Local", "unexpected": "field"}
        )
    with pytest.raises(ValidationError):
        UserUpdateRequest.model_validate(
            {"active": True, "display_name": "Admin", "manual_roles": ["admin"], "password": "leak"}
        )
