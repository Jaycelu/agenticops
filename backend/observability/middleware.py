from __future__ import annotations

import re
import time
import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from observability.context import request_id_var
from observability.metrics import metrics_registry


_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{8,80}$")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            with logger.contextualize(request_id=request_id, method=request.method, path=request.url.path):
                response = await call_next(request)
                duration_ms = (time.perf_counter() - started) * 1000
                metrics_registry.increment(
                    "agenticops_http_requests_total",
                    method=request.method,
                    route=request.scope.get("route").path if request.scope.get("route") else "unmatched",
                    status=str(response.status_code),
                )
                logger.bind(status=response.status_code, duration_ms=round(duration_ms, 3)).info("http_request_completed")
                response.headers["X-Request-ID"] = request_id
                return response
        finally:
            request_id_var.reset(token)
