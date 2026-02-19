from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from api.schemas.common import PageMeta


class AlertItem(BaseModel):
    eventid: str
    name: str
    severity: str
    severity_level: int
    host: str
    clock: Optional[str] = None
    acknowledged: int = 0
    status: str


class AlertListResponse(BaseModel):
    count: int = Field(ge=0)
    alerts: List[AlertItem] = Field(default_factory=list)


class ProblemItem(BaseModel):
    eventid: str
    name: str
    severity: str
    severity_level: int
    host: str
    clock: Optional[str] = None
    r_clock: Optional[str] = None
    acknowledged: int = 0
    status: str


class ProblemListResponse(BaseModel):
    count: int = Field(ge=0)
    problems: List[ProblemItem] = Field(default_factory=list)


class HostItem(BaseModel):
    hostid: str
    host: str
    name: str
    ip: Optional[str] = None
    status: str
    groups: List[str] = Field(default_factory=list)


class HostListResponse(BaseModel):
    count: int = Field(ge=0)
    hosts: List[HostItem] = Field(default_factory=list)


class TriggerItem(BaseModel):
    triggerid: str
    description: str
    severity: str
    severity_level: int
    host: str
    status: str
    value: str


class TriggerListResponse(BaseModel):
    count: int = Field(ge=0)
    triggers: List[TriggerItem] = Field(default_factory=list)


class AlertStatisticsResponse(BaseModel):
    total_alerts: int = Field(ge=0)
    acknowledged: int = Field(ge=0)
    unacknowledged: int = Field(ge=0)
    severity_stats: Dict[str, int] = Field(default_factory=dict)
    total_hosts: int = Field(ge=0)
    enabled_hosts: int = Field(ge=0)
    disabled_hosts: int = Field(ge=0)


class AcknowledgeRequest(BaseModel):
    event_ids: List[str]
    message: str = "已通过NetOps平台确认"


class AcknowledgeResponse(BaseModel):
    count: int = Field(ge=0)
    event_ids: List[str] = Field(default_factory=list)
    message: str


class AlertEventCreateRequest(BaseModel):
    source: str = "AUTOMATION"
    external_event_id: Optional[str] = None
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    host: Optional[str] = None
    name: str
    severity: str = "warning"
    severity_level: int = 2
    occurred_at: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    dedup_key: Optional[str] = None


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


class AlertEventListResponse(BaseModel):
    page: PageMeta
    events: List[AlertEventItem] = Field(default_factory=list)
