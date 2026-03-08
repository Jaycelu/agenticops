from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import PageMeta


class EventRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_event_id: Optional[int] = None
    source: str
    source_label: Optional[str] = None
    source_category: Optional[str] = None
    event_type: Optional[str] = None
    signal_key: Optional[str] = None
    disposition: Optional[str] = None
    disposition_reason: Optional[str] = None
    decision_confidence: Optional[float] = None
    cluster_key: Optional[str] = None
    correlation_key: Optional[str] = None
    signal_family: Optional[str] = None
    external_event_id: Optional[str] = None
    dedup_key: str
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    host: Optional[str] = None
    name: str
    severity: str
    severity_level: int
    status: str
    acknowledged: bool
    occurred_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    case_id: Optional[int] = None
    case_code: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EventIngestRequest(BaseModel):
    source: str = Field(default="ELK", max_length=50, description="Only ELK or ZABBIX are accepted")
    event_type: str = Field(default="log_signal", max_length=100, description="Only log_signal or zabbix_alert are accepted")
    external_event_id: Optional[str] = Field(default=None, max_length=128)
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    host: Optional[str] = Field(default=None, max_length=255)
    name: str = Field(..., min_length=1, max_length=512)
    severity: Optional[str] = Field(default=None, max_length=30)
    severity_level: Optional[int] = Field(default=None, ge=0, le=5)
    occurred_at: Optional[datetime] = None
    fingerprint: Optional[str] = Field(default=None, max_length=256)
    tags: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class EventIngestResponse(BaseModel):
    accepted: bool = True
    observe_only: bool
    event: EventRecord
    case_id: Optional[int] = None
    case_code: Optional[str] = None


class EventListResponse(BaseModel):
    page: PageMeta
    events: List[EventRecord] = Field(default_factory=list)


class EventClusterItem(BaseModel):
    cluster_key: str
    correlation_key: str
    title: str
    event_count: int
    source_categories: List[str] = Field(default_factory=list)
    dispositions: Dict[str, int] = Field(default_factory=dict)
    case_count: int = 0
    ticket_count: int = 0
    highest_severity: str = "warning"
    host: Optional[str] = None
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    latest_occurred_at: Optional[datetime] = None
    signal_family: Optional[str] = None
    device_name: Optional[str] = None
    device_role: Optional[str] = None
    site_name: Optional[str] = None
    topology_hint: Optional[str] = None
    root_cause_candidate: Optional[str] = None
    adjacent_devices: List[str] = Field(default_factory=list)
    link_count: int = 0
    impact_scope: Optional[str] = None


class EventClusterListResponse(BaseModel):
    clusters: List[EventClusterItem] = Field(default_factory=list)


class RootCauseCandidateItem(BaseModel):
    candidate_key: str
    title: str
    root_cause_candidate: str
    site_name: Optional[str] = None
    signal_family: Optional[str] = None
    score: float
    ranking_reason: str
    merged_cluster_count: int = 0
    event_count: int = 0
    case_count: int = 0
    ticket_count: int = 0
    source_categories: List[str] = Field(default_factory=list)
    adjacent_devices: List[str] = Field(default_factory=list)
    representative_device: Optional[str] = None
    impact_scope: Optional[str] = None
    recommended_actions: List[Dict[str, Any]] = Field(default_factory=list)


class RootCauseCandidateListResponse(BaseModel):
    items: List[RootCauseCandidateItem] = Field(default_factory=list)


class EventDispatchRequest(BaseModel):
    reviewer: Optional[str] = "system"


class EventDispositionRequest(BaseModel):
    disposition: str = Field(..., description="noise|ticket_only|case_required")
    reason: Optional[str] = None


class EventDispatchResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[int] = None
    case_id: Optional[int] = None
    case_code: Optional[str] = None
    playbook_check: Dict[str, Any] = Field(default_factory=dict)


class EventTicketCreateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = "P3"
    requester: Optional[str] = "netops-automation"


class EventTicketResponse(BaseModel):
    success: bool
    message: str
    ticket_id: Optional[str] = None
    provider: Optional[str] = None


class EventTaskLinkItem(BaseModel):
    task_id: int
    task_code: str
    status: str
    source_model: Optional[str] = None
    case_id: Optional[int] = None
    created_at: Optional[datetime] = None


class EventCaseLinkItem(BaseModel):
    case_id: int
    case_code: str
    created_at: Optional[str] = None


class EventRelationsResponse(BaseModel):
    event_id: int
    ticket: Dict[str, Any] = Field(default_factory=dict)
    linked_case: Optional[EventCaseLinkItem] = None
    linked_tasks: List[EventTaskLinkItem] = Field(default_factory=list)


class EventPlaybookDraftRequest(BaseModel):
    include_playbook: bool = True


class EventPlaybookDraftResponse(BaseModel):
    success: bool
    message: str
    event_id: int
    playbook_check: Dict[str, Any] = Field(default_factory=dict)
    playbook_yaml: str = ""


# Backward-compatible alias during event-domain migration.
AlertEventItem = EventRecord
