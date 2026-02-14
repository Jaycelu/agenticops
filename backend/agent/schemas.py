from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class Intent(BaseModel):
    intent: str = Field(..., description="User intent type")
    targets: List[str] = Field(default_factory=list, description="Target devices or objects")
    role: Optional[str] = Field(None, description="Device role (e.g., 核心交换机, 接入交换机)")
    site: Optional[str] = Field(None, description="Site name (e.g., 德阳, 成都)")
    time_range: Optional[str] = Field(None, description="Time range for queries")
    tools: List[str] = Field(default_factory=list, description="Required tools")
    risk_level: str = Field(default="read_only", description="Risk level")
    automation_type: Optional[str] = Field(None, description="Automation task type (backup_config, inspection, health_check)")
    backup_type: Optional[str] = Field(None, description="Backup type (full, running, startup)")
    inspection_template: Optional[str] = Field(None, description="Inspection template ID")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Intent confidence score")
    needs_clarification: bool = Field(default=False, description="Whether clarification is required")
    missing_slots: List[str] = Field(default_factory=list, description="Missing slots for execution")
    clarification_question: Optional[str] = Field(None, description="Suggested clarification question")


class ExecutionStep(BaseModel):
    step_id: str
    tool: str
    action: str
    params: Dict[str, Any]
    status: Literal["pending", "running", "completed", "failed"]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ExecutionPlan(BaseModel):
    plan_id: str
    intent: Intent
    steps: List[ExecutionStep]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    execution_plan: Optional[ExecutionPlan] = None
    execution_results: Optional[List[ExecutionStep]] = None
    trace_id: str
