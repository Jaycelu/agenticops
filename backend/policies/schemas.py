from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


class RiskLevel(IntEnum):
    READ_ONLY = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    DESTRUCTIVE = 4


class AutonomyLevel(IntEnum):
    """System-wide autonomy ladder (Phase 4)."""
    OBSERVE_ONLY = 0       # block all actions (incl. notifications)
    RECOMMEND = 1          # current 'observe_only': allow notifications + observe-mode reads; block mutations
    ASSISTED = 2           # default 'auto': allow low-risk (R<2) auto; R>=2 needs approval
    GUARDED = 3            # allow R<3 auto; R>=3 needs approval
    AUTONOMOUS = 4         # allow R<4 auto; R==4 destructive needs approval
    SELF_OPTIMIZING = 5    # same enforcement as L4; flag for adaptive tuning


AUTONOMY_LEVEL_NAMES = {
    0: "observe_only",
    1: "recommend",
    2: "assisted",
    3: "guarded",
    4: "autonomous",
    5: "self_optimizing",
}

# Risk threshold at or above which approval is required, per autonomy level.
APPROVAL_THRESHOLD_BY_LEVEL = {
    0: 1,  # L0 blocks everything anyway
    1: 1,  # L1 (observe): any risk needs approval (also runtime-blocked)
    2: 2,  # L2 (assisted): R>=2 needs approval (matches Phase 1 behavior)
    3: 3,  # L3 (guarded): R>=3 needs approval
    4: 4,  # L4 (autonomous): R>=4 needs approval
    5: 4,  # L5: same as L4
}


@dataclass
class GateResult:
    gate: str
    passed: bool
    reason: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "passed": self.passed,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass
class PolicyDecision:
    allowed: bool
    effective_risk: int
    gate_results: List[GateResult] = field(default_factory=list)
    required_approval: bool = False
    blocked_reason: Optional[str] = None
    audit: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "effective_risk": self.effective_risk,
            "required_approval": self.required_approval,
            "blocked_reason": self.blocked_reason,
            "gate_results": [item.to_dict() for item in self.gate_results],
            "audit": self.audit,
        }
