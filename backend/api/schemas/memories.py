from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryEntryResponse(BaseModel):
    id: int
    case_id: Optional[int] = None
    memory_type: str
    memory_key: str
    title: str
    summary: Optional[str] = None
    source: str
    tags: List[str] = Field(default_factory=list)
    confidence: float
    success_score: float
    content: Dict[str, Any] = Field(default_factory=dict)
    last_accessed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class MemoryListResponse(BaseModel):
    total: int
    items: List[MemoryEntryResponse]


class MemoryOverviewResponse(BaseModel):
    total_memories: int
    by_type: Dict[str, int] = Field(default_factory=dict)
    high_confidence_patterns: int
    successful_outcomes: int
