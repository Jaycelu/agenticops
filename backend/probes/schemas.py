from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probe_id: str = Field(min_length=1, max_length=120)
    netbox_device_id: int = Field(gt=0)
    credential_id: int = Field(gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)


class EvidenceEnvelope(BaseModel):
    probe_id: str
    template_version: str
    netbox_device_id: int
    collected_at: datetime
    outputs: list[dict[str, Any]]
    redactions: int = 0
    truncated: bool = False


class ProbeResult(BaseModel):
    run_id: int
    status: Literal["succeeded", "failed", "rejected"]
    evidence: EvidenceEnvelope | None = None
    error_code: str | None = None
