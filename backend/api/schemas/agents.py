from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentCatalogItemResponse(BaseModel):
    agent_type: str
    name: str
    purpose: str
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)


class AgentHealthItemResponse(BaseModel):
    agent_type: str
    total_runs: int
    running_runs: int
    failed_runs: int
    last_run_at: Optional[datetime] = None


class AgentRunResponse(BaseModel):
    id: int
    case_id: int
    agent_type: str
    agent_name: str
    status: str
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    output_payload: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class AgentClaimResponse(BaseModel):
    id: int
    case_id: int
    agent_run_id: int
    agent_type: str
    claim_type: str
    claim_text: str
    status: str
    confidence: float
    evidence_refs: List[Any] = Field(default_factory=list)
    gaps: List[Any] = Field(default_factory=list)
    claim_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class AgentRunListResponse(BaseModel):
    total: int
    items: List[AgentRunResponse]


class AgentHealthResponse(BaseModel):
    items: List[AgentHealthItemResponse]
