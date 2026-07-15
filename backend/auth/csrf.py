from __future__ import annotations

import hmac
import logging
from datetime import datetime, timezone

from fastapi.responses import JSONResponse

from auth.session_service import secret_digest
from config.settings import settings
from database import SessionLocal
from models.auth import AuthSession


UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
EXEMPT_PATH_PREFIXES = ("/api/auth/login/", "/api/auth/callback/")
logger = logging.getLogger(__name__)


class CSRFMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"].upper() not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path.startswith(EXEMPT_PATH_PREFIXES):
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request

        request = Request(scope, receive=receive)
        session_token = request.cookies.get(settings.auth_cookie_name)
        if not session_token:
            await self.app(scope, receive, send)
            return
        csrf_cookie = request.cookies.get(settings.auth_csrf_cookie_name, "")
        csrf_header = request.headers.get("x-csrf-token", "")
        valid = bool(csrf_cookie and csrf_header and hmac.compare_digest(csrf_cookie, csrf_header))
        if valid:
            db = SessionLocal()
            try:
                auth_session = (
                    db.query(AuthSession)
                    .filter(AuthSession.id == secret_digest(session_token))
                    .first()
                )
                now = datetime.now(timezone.utc)
                if auth_session is None:
                    valid = False
                else:
                    expires_at = auth_session.expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    valid = (
                        auth_session.revoked_at is None
                        and expires_at > now
                        and hmac.compare_digest(
                            auth_session.csrf_token_hash,
                            secret_digest(csrf_header),
                        )
                    )
            finally:
                db.close()
        if not valid:
            logger.warning("csrf_validation_failed method=%s path=%s", scope["method"], path)
            response = JSONResponse(status_code=403, content={"detail": "csrf_validation_failed"})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
