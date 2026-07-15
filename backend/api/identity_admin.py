from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth.dependencies import require_permissions
from auth.identity_admin_service import identity_admin_service
from auth.rbac import Permission
from auth.schemas import Principal
from database import get_db


router = APIRouter(prefix="/api/admin/identity", tags=["identity-administration"])


class ProviderUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_type: str
    display_name: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)
    clear_secrets: set[str] = Field(default_factory=set)
    group_role_mapping: dict[str, Any] = Field(default_factory=dict)


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool
    display_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    manual_roles: set[str] = Field(default_factory=set)


@router.get("/providers")
def list_identity_providers(
    principal: Principal = Depends(require_permissions(Permission.IDENTITIES_MANAGE.value)),
    db: Session = Depends(get_db),
):
    del principal
    return {"items": identity_admin_service.list_providers(db)}


@router.put("/providers/{provider_key}")
def upsert_identity_provider(
    provider_key: str,
    payload: ProviderUpsertRequest,
    principal: Principal = Depends(require_permissions(Permission.IDENTITIES_MANAGE.value)),
    db: Session = Depends(get_db),
):
    try:
        return identity_admin_service.upsert_provider(
            db,
            provider_key=provider_key,
            provider_type=payload.provider_type,
            display_name=payload.display_name,
            enabled=payload.enabled,
            config=payload.config,
            secrets=payload.secrets,
            clear_secrets=payload.clear_secrets,
            group_role_mapping=payload.group_role_mapping,
            actor=principal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/users")
def list_users(
    principal: Principal = Depends(require_permissions(Permission.USERS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    del principal
    return {"items": identity_admin_service.list_users(db)}


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    principal: Principal = Depends(require_permissions(Permission.USERS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    try:
        return identity_admin_service.update_user(
            db,
            user_id=user_id,
            active=payload.active,
            display_name=payload.display_name,
            email=payload.email,
            manual_roles=payload.manual_roles,
            actor=principal,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
