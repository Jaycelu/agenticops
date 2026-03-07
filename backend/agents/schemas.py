from dataclasses import dataclass, field
from typing import Any, Dict, List


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

