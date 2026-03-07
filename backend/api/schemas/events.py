from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import PageMeta


class AlertEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EventIngestRequest(BaseModel):
    source: str = Field(default="SPLUNK", max_length=50)
    event_type: str = Field(default="unknown", max_length=100)
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


class SplunkWebhookRequest(BaseModel):
    search_name: Optional[str] = None
    sid: Optional[str] = None
    host: Optional[str] = None
    source: Optional[str] = None
    sourcetype: Optional[str] = None
    time: Optional[str] = None
    event: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)


class EDAWebhookRequest(BaseModel):
    rulebook: Optional[str] = None
    rule_name: Optional[str] = None
    event_id: Optional[str] = None
    source: Optional[str] = None
    occurred_at: Optional[str] = None
    severity: Optional[str] = None
    event: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    auto_dispatch_readonly: bool = True
    reviewer: Optional[str] = "eda-system"


class EventIngestResponse(BaseModel):
    accepted: bool = True
    observe_only: bool
    event: AlertEventItem
    case_id: Optional[int] = None
    case_code: Optional[str] = None


class EventIngestDispatchResult(BaseModel):
    dispatched: bool = False
    task_id: Optional[int] = None
    message: str = ""


class EDAIngestResponse(BaseModel):
    accepted: bool = True
    observe_only: bool
    event: AlertEventItem
    dispatch: EventIngestDispatchResult
    case_id: Optional[int] = None
    case_code: Optional[str] = None


class EventListResponse(BaseModel):
    page: PageMeta
    events: List[AlertEventItem] = Field(default_factory=list)


class EventDispatchRequest(BaseModel):
    reviewer: Optional[str] = "system"


class EventDispatchResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[int] = None
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
    created_at: Optional[datetime] = None


class EventRelationsResponse(BaseModel):
    event_id: int
    ticket: Dict[str, Any] = Field(default_factory=dict)
    linked_tasks: List[EventTaskLinkItem] = Field(default_factory=list)


class EventPlaybookDraftRequest(BaseModel):
    include_playbook: bool = True


class EventPlaybookDraftResponse(BaseModel):
    success: bool
    message: str
    event_id: int
    playbook_check: Dict[str, Any] = Field(default_factory=dict)
    playbook_yaml: str = ""
