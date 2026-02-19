from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    meta: Optional[Dict[str, Any]] = None


class PageMeta(BaseModel):
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)
    returned: int = Field(ge=0)
    has_more: bool


def error_detail(code: str, message: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"code": code, "message": message}
    if meta is not None:
        payload["meta"] = meta
    return payload
