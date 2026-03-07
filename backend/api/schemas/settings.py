from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    id: str
    name: str
    provider: str
    api_key: str
    api_url: str
    model: str
    is_active: bool = False
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ModelUpdateRequest(BaseModel):
    model_id: str
    name: Optional[str] = None
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ModelCreateRequest(BaseModel):
    name: str
    provider: str
    api_key: str
    api_url: str
    model: str
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IntegrationConfigPayload(BaseModel):
    enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    secrets: Dict[str, str] = Field(default_factory=dict)
    clear_secrets: list[str] = Field(default_factory=list)


class IntegrationConfigResponse(BaseModel):
    integration_type: str
    display_name: str
    enabled: bool
    config: Dict[str, Any] = Field(default_factory=dict)
    secret_status: Dict[str, bool] = Field(default_factory=dict)
    updated_at: Optional[str] = None
    source: str = "database"


class IntegrationTestResponse(BaseModel):
    success: bool
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class LogScopePayload(BaseModel):
    scope_key: str
    display_name: str
    netbox_site_id: Optional[int] = None
    site_code_snapshot: Optional[str] = None
    site_name_snapshot: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    query_filter: str
    default_time_range: str = "-1d,now"
    enabled: bool = True
    sort_order: int = 100
    scope_metadata: Dict[str, Any] = Field(default_factory=dict)


class LogScopeResponse(BaseModel):
    id: int
    scope_key: str
    display_name: str
    netbox_site_id: Optional[int] = None
    site_code_snapshot: Optional[str] = None
    site_name_snapshot: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    query_filter: str
    default_time_range: str
    enabled: bool
    sort_order: int
    scope_metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None
