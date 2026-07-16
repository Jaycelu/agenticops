from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CaseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    source_type: str = Field(..., min_length=1, max_length=50)
    source_system: str = Field(..., min_length=1, max_length=50)
    dedup_key: str = Field(..., min_length=1, max_length=128)
    severity: str = Field(default="warning", max_length=30)
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    device_ip: Optional[str] = None
    host: Optional[str] = None
    summary: Optional[str] = None
    occurred_at: Optional[datetime] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    case_metadata: Dict[str, Any] = Field(default_factory=dict)


class CaseIntakeRequest(CaseCreateRequest):
    base_name: Optional[str] = None
    log_query: Optional[str] = None
    time_range: str = "-15m,now"
    log_limit: int = Field(default=200, ge=1, le=1000)
    run_pipeline: bool = True
    credential_id: Optional[int] = None


class SourceEventResponse(BaseModel):
    id: int
    source_type: str
    source_system: str
    external_event_id: Optional[str] = None
    dedup_key: str
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    device_ip: Optional[str] = None
    host: Optional[str] = None
    title: str
    severity: str
    status: str
    occurred_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None


class CaseSummaryResponse(BaseModel):
    id: int
    case_code: str
    title: str
    summary: Optional[str] = None
    source_event_id: Optional[int] = None
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    device_ip: Optional[str] = None
    host: Optional[str] = None
    priority: str
    risk_level: str
    status: str
    current_phase: str
    opened_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None


class EvidenceItemResponse(BaseModel):
    id: int
    evidence_type: str
    source_system: str
    source_ref: Optional[str] = None
    fingerprint: Optional[str] = None
    device_ip: Optional[str] = None
    host: Optional[str] = None
    occurred_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    confidence: float
    summary: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class CaseDetailResponse(CaseSummaryResponse):
    case_metadata: Dict[str, Any] = Field(default_factory=dict)
    closed_at: Optional[datetime] = None
    source_event: Optional[SourceEventResponse] = None


class CaseListResponse(BaseModel):
    total: int
    items: List[CaseSummaryResponse]


class CaseOverviewResponse(BaseModel):
    total_cases: int
    open_cases: int
    executing_cases: int
    resolved_cases: int
    high_risk_cases: int
    by_phase: Dict[str, int] = Field(default_factory=dict)


class CasePipelineResponse(BaseModel):
    case_id: int
    status: str = "accepted"
    execution_mode: str = "async"
    graph_run_id: Optional[str] = None
    current_state: Optional[str] = None
    current_node: Optional[str] = None
    queued: bool = False
    already_running: bool = False
    message: Optional[str] = None
    legacy_result: Optional[Dict[str, Any]] = None
    agent_run_ids: List[int] = Field(default_factory=list)
    claim_ids: List[int] = Field(default_factory=list)
    remediation_plan_id: Optional[int] = None
