from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentExecutionContext:
    case_id: int
    case_code: str
    title: str
    summary: str
    source_system: str
    source_payload: Dict[str, Any]
    normalized_payload: Dict[str, Any]
    site_id: int | None = None
    netbox_device_id: int | None = None
    device_ip: str | None = None
    host: str | None = None
    evidence_items: List[Dict[str, Any]] = field(default_factory=list)
    prior_claims: List[Dict[str, Any]] = field(default_factory=list)
    memory_hits: List[Dict[str, Any]] = field(default_factory=list)
    runtime: Dict[str, Any] = field(default_factory=dict)
    # Harness contracts (serialized dicts; see harness.contracts)
    evidence_bundle: Dict[str, Any] = field(default_factory=dict)
    episode_goal: Dict[str, Any] = field(default_factory=dict)
    insight_round: int = 0
    harness_trace: List[str] = field(default_factory=list)


@dataclass
class AgentDecision:
    summary: str
    confidence: float
    claim_type: str
    claim_text: str
    status: str
    evidence_refs: List[Any] = field(default_factory=list)
    gaps: List[Any] = field(default_factory=list)
    output_payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Orchestrator may act on these for branching / follow-up collection
    next_evidence_requests: List[Dict[str, Any]] = field(default_factory=list)
    cited_evidence_item_ids: List[int] = field(default_factory=list)
    stopped_reason: Optional[str] = None

