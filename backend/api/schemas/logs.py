from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BaseConfigItem(BaseModel):
    key: str
    name: str
    filter: str
    time_range: str


class BaseConfigsResponse(BaseModel):
    bases: List[BaseConfigItem] = Field(default_factory=list)


class LogEntry(BaseModel):
    timestamp: str = ""
    hostname: str = "Unknown"
    message: str = ""
    level: str = "unknown"
    raw: Dict[str, Any] = Field(default_factory=dict)
    device_ip: Optional[str] = None


class LogsResponse(BaseModel):
    base: Optional[str] = None
    base_name_cn: Optional[str] = None
    query: Optional[str] = None
    time_range: Optional[str] = None
    total: int = 0
    logs: List[LogEntry] = Field(default_factory=list)
    no_logs_hint: Optional[bool] = None
    timeout_error: Optional[bool] = None


class LevelGroup(BaseModel):
    level: str
    count: int
    time_range: str
    logs: List[Dict[str, Any]] = Field(default_factory=list)


class AggregatedGroup(BaseModel):
    device: str
    total_count: int
    level_groups: List[LevelGroup] = Field(default_factory=list)


class AggregationResponse(BaseModel):
    success: bool
    total_logs: int = 0
    total_available: int = 0
    aggregated_groups: List[AggregatedGroup] = Field(default_factory=list)
    has_more: bool = False
