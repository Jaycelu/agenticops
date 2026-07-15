from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ELKDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=512)
    timestamp: datetime
    message: str
    device_key: str = Field(min_length=1, max_length=255)
    severity: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ELKPage(BaseModel):
    documents: list[ELKDocument]
    has_more: bool
    total: int | None = None
