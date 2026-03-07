from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RemediationPlanResponse(BaseModel):
    id: int
    case_id: int
    plan_code: str
    generated_by_agent_run_id: Optional[int] = None
    status: str
    execution_mode: str
    approval_status: str
    risk_level: str
    summary: Optional[str] = None
    plan_payload: Dict[str, Any] = Field(default_factory=dict)
    rollback_payload: Dict[str, Any] = Field(default_factory=dict)
    safety_checks: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None


class ExecutionRunResponse(BaseModel):
    id: int
    case_id: int
    remediation_plan_id: int
    executor_type: str
    executor_name: str
    status: str
    command_summary: Optional[str] = None
    request_payload: Dict[str, Any] = Field(default_factory=dict)
    result_payload: Dict[str, Any] = Field(default_factory=dict)
    audit_trail: List[Any] = Field(default_factory=list)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


class RemediationPlanListResponse(BaseModel):
    total: int
    items: List[RemediationPlanResponse]


class ExecutionRunListResponse(BaseModel):
    total: int
    items: List[ExecutionRunResponse]


class FabricOverviewResponse(BaseModel):
    total_plans: int
    draft_plans: int
    approved_plans: int
    running_executions: int
    failed_executions: int
