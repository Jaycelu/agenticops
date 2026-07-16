from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    netbox_device_id: int = Field(gt=0)


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    probe_id: str = Field(pattern=r"^[a-z0-9_.-]{3,120}$")
    target: EvidenceTarget
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=3, max_length=1000)
    expected_evidence_type: Literal["command_output", "metric", "log", "topology", "external_context"]


class HypothesisContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis_code: str = Field(min_length=1, max_length=120)
    cause_code: str = Field(min_length=1, max_length=120)
    cause: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[int] = Field(default_factory=list)
    contradicting_evidence_ids: list[int] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_probe_requests: list[EvidenceRequest] = Field(default_factory=list)
    status: Literal["proposed", "supported", "weakened", "rejected", "confirmed"] = "proposed"


class CriticDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["accept", "revise", "reject"]
    reason: str = Field(min_length=1)
    cited_evidence_ids: list[int] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)


class SupervisorTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_state: str = Field(alias="from")
    to_state: str = Field(alias="to")


class SupervisorTaskDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_type: str
    graph_node: str
    goal: str
    assigned_agent_type: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100


class SupervisorDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal[
        "collect_more_evidence", "run_diagnostics", "run_critic", "plan", "safety_review",
        "wait_agents", "wait_human", "observe_only_stop", "escalate", "complete",
    ]
    next_tasks: list[SupervisorTaskDecision] = Field(default_factory=list)
    state_transition: SupervisorTransition | None = None
    reason: str
    stop_reason: str | None = None

    @model_validator(mode="after")
    def require_work_or_stop(self):
        if not self.next_tasks and not self.stop_reason and self.decision not in {"wait_agents", "wait_human", "complete"}:
            raise ValueError("supervisor decision must create work or provide a stop reason")
        return self
