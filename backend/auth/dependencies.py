from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from auth.schemas import Principal
from auth.api_token_service import api_token_service
from auth.session_service import auth_session_service
from config.settings import settings
from database import get_db


def get_current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication_required")
    principal = auth_session_service.resolve_principal(db, token)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_or_expired_session")
    return principal


def require_permissions(*required: str) -> Callable[..., Principal]:
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        missing = sorted(set(required) - set(principal.permissions))
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "permission_denied", "missing": missing},
            )
        return principal

    return dependency


def get_api_token_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="api_token_required")
    principal = api_token_service.authenticate(db, value.strip())
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_or_expired_api_token")
    return principal


def require_api_permissions(*required: str) -> Callable[..., Principal]:
    def dependency(principal: Principal = Depends(get_api_token_principal)) -> Principal:
        missing = sorted(set(required) - set(principal.permissions))
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "permission_denied", "missing": missing},
            )
        return principal

    return dependency
