from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from observability.context import request_id


def error_payload(code: str, message: str, details=None) -> dict:
    # Keep ``detail`` during the API migration so existing clients remain compatible.
    payload = {
        "detail": message,
        "error": {"code": code, "message": message, "request_id": request_id()},
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload("http_error", str(exc.detail)),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        del request
        details = [
            {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in exc.errors()
        ]
        return JSONResponse(status_code=422, content=error_payload("validation_error", "request validation failed", details))

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        del request
        logger.bind(error_type=type(exc).__name__).exception("unhandled_request_error")
        return JSONResponse(status_code=500, content=error_payload("internal_error", "internal server error"))
