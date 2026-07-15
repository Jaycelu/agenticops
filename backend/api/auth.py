from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import get_current_principal
from auth.schemas import Principal, SessionCredentials
from auth.service import AuthenticationFailed, LoginResult, authentication_service
from auth.session_service import auth_session_service
from config.settings import settings
from database import get_db


router = APIRouter(prefix="/api/auth", tags=["authentication"])


class CredentialLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=4096)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _callback_url(request: Request, provider_key: str) -> str:
    path = f"/api/auth/callback/{provider_key}"
    del request
    parsed = urlparse(settings.auth_public_base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_PUBLIC_BASE_URL must be configured as an absolute HTTPS URL for SSO",
        )
    return f"{settings.auth_public_base_url.rstrip('/')}{path}"


def _set_auth_cookies(response: Response, credentials: SessionCredentials) -> None:
    max_age = max(0, int((credentials.expires_at - datetime.now(timezone.utc)).total_seconds()))
    common = {
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
        "max_age": max_age,
    }
    response.set_cookie(
        settings.auth_cookie_name,
        credentials.session_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        credentials.csrf_token,
        httponly=False,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.auth_csrf_cookie_name, path="/")


def _principal_payload(principal: Principal) -> dict[str, object]:
    return {
        "id": principal.user_id,
        "username": principal.username,
        "display_name": principal.display_name,
        "roles": sorted(principal.roles),
        "permissions": sorted(principal.permissions),
    }


def _login_response(result: LoginResult) -> JSONResponse:
    response = JSONResponse(
        {
            "user": _principal_payload(result.principal),
            "expires_at": result.credentials.expires_at.isoformat(),
        }
    )
    _set_auth_cookies(response, result.credentials)
    return response


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)):
    return {"items": authentication_service.list_enabled_providers(db)}


@router.post("/login/{provider_key}")
async def credential_login(
    provider_key: str,
    payload: CredentialLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        result = await authentication_service.authenticate_credentials(
            db,
            provider_key=provider_key,
            username=payload.username,
            password=payload.password,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationFailed as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication_failed") from exc
    return _login_response(result)


@router.get("/login/{provider_key}/start")
async def redirect_login_start(provider_key: str, request: Request, db: Session = Depends(get_db)):
    try:
        start = await authentication_service.begin_redirect_login(
            db,
            provider_key=provider_key,
            callback_url=_callback_url(request, provider_key),
        )
    except AuthenticationFailed as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="authentication_start_failed") from exc
    return RedirectResponse(start.redirect_url, status_code=status.HTTP_302_FOUND)


async def _complete_callback(
    provider_key: str,
    request: Request,
    request_data: dict[str, str],
    db: Session,
):
    try:
        result = await authentication_service.complete_redirect_login(
            db,
            provider_key=provider_key,
            callback_url=_callback_url(request, provider_key),
            request_data=request_data,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationFailed:
        query = urlencode({"status": "failed"})
        return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/auth/callback?{query}", status_code=303)
    response = RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}/auth/callback?{urlencode({'status': 'success'})}",
        status_code=303,
    )
    _set_auth_cookies(response, result.credentials)
    return response


@router.get("/callback/{provider_key}")
async def oidc_callback(provider_key: str, request: Request, db: Session = Depends(get_db)):
    return await _complete_callback(
        provider_key,
        request,
        {key: value for key, value in request.query_params.items()},
        db,
    )


@router.post("/callback/{provider_key}")
async def saml_callback(provider_key: str, request: Request, db: Session = Depends(get_db)):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            too_large = int(content_length) > 2 * 1024 * 1024
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid content length") from exc
        if too_large:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="SAML response too large")
    if len(await request.body()) > 2 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="SAML response too large")
    form = await request.form()
    return await _complete_callback(
        provider_key,
        request,
        {str(key): str(value) for key, value in form.items()},
        db,
    )


@router.get("/me")
def current_session(principal: Principal = Depends(get_current_principal)):
    return {"user": _principal_payload(principal)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    auth_session_service.revoke_session(db, principal.session_id)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(response)
    return response
