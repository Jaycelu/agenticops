from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EvidenceQuerySpec:
    """Read-only collection parameters used to build the evidence bundle (replay harness)."""

    elk_base_name: Optional[str] = None
    elk_query: Optional[str] = None
    elk_time_range: str = "-15m,now"
    elk_limit: int = 200
    netbox_device_id: Optional[int] = None
    zabbix_host: Optional[str] = None


@dataclass
class EvidenceBundle:
    """Versioned snapshot of what the case harness collected before agent steps."""

    version: str = "v1"
    collected_at: str = field(default_factory=_utc_now_iso)
    case_id: int = 0
    case_code: str = ""
    queries: EvidenceQuerySpec = field(default_factory=EvidenceQuerySpec)
    evidence_item_ids: List[int] = field(default_factory=list)
    runtime_keys: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["queries"] = asdict(self.queries)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceBundle":
        q = data.get("queries") or {}
        spec = EvidenceQuerySpec(**{k: v for k, v in q.items() if k in EvidenceQuerySpec.__dataclass_fields__})
        return cls(
            version=str(data.get("version") or "v1"),
            collected_at=str(data.get("collected_at") or _utc_now_iso()),
            case_id=int(data.get("case_id") or 0),
            case_code=str(data.get("case_code") or ""),
            queries=spec,
            evidence_item_ids=list(data.get("evidence_item_ids") or []),
            runtime_keys=list(data.get("runtime_keys") or []),
            notes=list(data.get("notes") or []),
        )


@dataclass
class EpisodeGoal:
    """Explicit termination / success criteria for a case harness episode."""

    kind: str = "diagnose_and_plan"
    description: str = ""
    min_insight_confidence: float = 0.55
    require_remediation_plan: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodeGoal":
        return cls(
            kind=str(data.get("kind") or "diagnose_and_plan"),
            description=str(data.get("description") or ""),
            min_insight_confidence=float(data.get("min_insight_confidence") or 0.55),
            require_remediation_plan=bool(data.get("require_remediation_plan", True)),
        )


@dataclass
class AgentStepResult:
    """Structured outcome of one harness step (aligns with AgentDecision + trace metadata)."""

    agent_type: str
    agent_name: str
    claim_type: str
    status: str
    confidence: float
    summary: str
    output_payload: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[Any] = field(default_factory=list)
    gaps: List[Any] = field(default_factory=list)
    harness_round: int = 0
    stopped_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_evidence_bundle_dict(
    *,
    case_id: int,
    case_code: str,
    queries: EvidenceQuerySpec,
    evidence_item_ids: List[int],
    runtime: Dict[str, Any],
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    bundle = EvidenceBundle(
        case_id=case_id,
        case_code=case_code,
        queries=queries,
        evidence_item_ids=evidence_item_ids,
        runtime_keys=sorted(runtime.keys()),
        notes=notes or [],
    )
    return bundle.to_dict()
