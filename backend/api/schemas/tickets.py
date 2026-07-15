from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import PageMeta


class LocalTicketItem(BaseModel):
    id: int
    ticket_code: str
    provider: str
    event_id: Optional[int] = None
    source_event_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: str
    requester: str
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LocalTicketListResponse(BaseModel):
    page: PageMeta
    tickets: List[LocalTicketItem] = Field(default_factory=list)


class LocalTicketUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    comment: Optional[str] = None


class LocalTicketUpdateResponse(BaseModel):
    success: bool
    message: str
    ticket: Optional[LocalTicketItem] = None
