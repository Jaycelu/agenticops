from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from config import pipeline_thresholds
from config.settings import settings
from models.agenticops import ExecutionRun, ExecutionRunStatus, RemediationPlan
from policies.rules import is_core_target, rule_snapshot
from policies.schemas import (
    APPROVAL_THRESHOLD_BY_LEVEL,
    AUTONOMY_LEVEL_NAMES,
    AutonomyLevel,
    GateResult,
    PolicyDecision,
)
from services.automation_settings_service import automation_settings_service
from tools.base import ToolRequest
from tools.registry import ToolRegistry, tool_registry


class PolicyGuard:
    def __init__(self, registry: Optional[ToolRegistry] = None) -> None:
        self.registry = registry or tool_registry

    def check(
        self,
        request: ToolRequest,
        *,
        case: Any = None,
        plan: Optional[RemediationPlan] = None,
        db: Optional[Session] = None,
    ) -> PolicyDecision:
        gates: list[GateResult] = []
        spec = self.registry.get(request.tool_id)
        if spec is None:
            gates.append(GateResult("schema", False, "unregistered_tool", {"tool_id": request.tool_id}))
            return self._decision(False, 4, gates, "unregistered_tool", request)

        valid, errors = self.registry.validate_params(spec, request.params)
        mode_allowed = request.mode in spec.modes if spec.modes else True
        if not valid or not mode_allowed:
            reason = "invalid_params" if not valid else "mode_not_allowed"
            gates.append(
                GateResult(
                    "schema",
                    False,
                    reason,
                    {"errors": errors, "mode": request.mode, "allowed_modes": spec.modes},
                )
            )
            return self._decision(False, spec.risk_level, gates, reason, request, spec=spec)
        gates.append(GateResult("schema", True, "ok", {"tool_id": spec.tool_id}))

        rules = rule_snapshot(request.target)
        gates.append(GateResult("rules", True, "rules_captured", rules))

        risk = int(spec.risk_level)
        blocked_patterns = self.registry.find_blocked_patterns(spec, request.params)
        allowlist_ok = self.registry.commands_match_allowlist(spec, request.params)
        if blocked_patterns:
            risk = max(risk, 3)
        if not allowlist_ok:
            risk = max(risk, 2)
        if is_core_target(request.target) and risk > 0:
            risk = min(4, risk + 1)
        gates.append(
            GateResult(
                "risk",
                True,
                "risk_calculated",
                {
                    "base_risk": spec.risk_level,
                    "effective_risk": risk,
                    "blocked_patterns": blocked_patterns,
                    "allowlist_ok": allowlist_ok,
                },
            )
        )

        autonomy_level = self._autonomy_level(db)
        approval_threshold = APPROVAL_THRESHOLD_BY_LEVEL.get(autonomy_level, 2)
        required_approval = bool(spec.requires_approval or risk >= approval_threshold)
        plan_approved = bool(plan and str(plan.approval_status).lower() == "approved")
        if required_approval and not plan_approved:
            gates.append(GateResult(
                "approval", False, "approval_required",
                {
                    "approval_status": getattr(plan, "approval_status", None),
                    "autonomy_level": autonomy_level,
                    "approval_threshold": approval_threshold,
                },
            ))
            return self._decision(False, risk, gates, "approval_required", request, spec=spec, required_approval=True, autonomy_level=autonomy_level)
        gates.append(GateResult(
            "approval", True, "approved" if required_approval else "not_required",
            {"autonomy_level": autonomy_level, "approval_threshold": approval_threshold},
        ))

        mutating = spec.capability == "mutation"

        # Gate 5a — autonomy floor:
        #   L0: block everything (including notifications).
        #   L1: block mutating non-notification (= historical observe_only).
        #   L2+: do not block here; risk vs. approval already enforced upstream.
        if autonomy_level <= AutonomyLevel.OBSERVE_ONLY:
            gates.append(GateResult(
                "runtime", False, "autonomy_block_all",
                {"autonomy_level": autonomy_level, "level_name": AUTONOMY_LEVEL_NAMES[autonomy_level]},
            ))
            return self._decision(False, risk, gates, "autonomy_block_all", request, spec=spec, required_approval=required_approval, autonomy_level=autonomy_level)
        if autonomy_level <= AutonomyLevel.RECOMMEND and mutating and spec.executor_type != "notification":
            gates.append(GateResult(
                "runtime", False, "observe_only_blocked",
                {"autonomy_level": autonomy_level, "level_name": AUTONOMY_LEVEL_NAMES[autonomy_level], "risk": risk},
            ))
            return self._decision(False, risk, gates, "observe_only_blocked", request, spec=spec, required_approval=required_approval, autonomy_level=autonomy_level)

        # Gate 5b — circuit breaker
        if db is not None and self._circuit_breaker_tripped(db, request):
            gates.append(GateResult(
                "runtime", False, "circuit_breaker",
                {
                    "window_minutes": pipeline_thresholds.EXECUTION_CIRCUIT_BREAKER_WINDOW_MINUTES,
                    "autonomy_level": autonomy_level,
                },
            ))
            return self._decision(False, risk, gates, "circuit_breaker", request, spec=spec, required_approval=required_approval, autonomy_level=autonomy_level)
        gates.append(GateResult(
            "runtime", True, "ok",
            {"autonomy_level": autonomy_level, "level_name": AUTONOMY_LEVEL_NAMES[autonomy_level]},
        ))

        if not spec.executable:
            gates.append(GateResult("execution", False, "tool_not_executable", {"tool_id": spec.tool_id}))
            return self._decision(False, risk, gates, "tool_not_executable", request, spec=spec, required_approval=required_approval, autonomy_level=autonomy_level)
        gates.append(GateResult("execution", True, "executable"))
        return self._decision(True, risk, gates, None, request, spec=spec, required_approval=required_approval, autonomy_level=autonomy_level)

    def _autonomy_level(self, db: Optional[Session]) -> int:
        """Phase 4: resolve current autonomy level (0..5). Defaults to L1 (recommend) when DB unavailable."""
        if db is None:
            return int(AutonomyLevel.RECOMMEND) if settings.automation_observe_only else int(AutonomyLevel.ASSISTED)
        try:
            return int(automation_settings_service.get_autonomy_level(db))
        except Exception:
            return int(AutonomyLevel.RECOMMEND) if settings.automation_observe_only else int(AutonomyLevel.ASSISTED)

    def _circuit_breaker_tripped(self, db: Session, request: ToolRequest) -> bool:
        target_id = request.target.get("netbox_device_id") or request.target.get("device_ip") or request.target.get("host")
        if not target_id:
            return False
        since = datetime.now(timezone.utc) - timedelta(minutes=pipeline_thresholds.EXECUTION_CIRCUIT_BREAKER_WINDOW_MINUTES)
        count = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.started_at >= since)
            .filter(ExecutionRun.status.in_([ExecutionRunStatus.SUCCEEDED, ExecutionRunStatus.VERIFIED, ExecutionRunStatus.FAILED]))
            .filter(ExecutionRun.request_payload["target_id"].as_string() == str(target_id))
            .count()
        )
        return count >= pipeline_thresholds.EXECUTION_CIRCUIT_BREAKER_MAX_RUNS

    def _decision(
        self,
        allowed: bool,
        risk: int,
        gates: list[GateResult],
        blocked_reason: Optional[str],
        request: ToolRequest,
        *,
        spec: Any = None,
        required_approval: bool = False,
        autonomy_level: Optional[int] = None,
    ) -> PolicyDecision:
        audit: Dict[str, Any] = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "tool_id": request.tool_id,
            "tool_name": getattr(spec, "name", None),
            "mode": request.mode,
            "requested_by": request.requested_by,
            "allowed": allowed,
            "effective_risk": risk,
            "blocked_reason": blocked_reason,
            "autonomy_level": autonomy_level,
            "autonomy_level_name": AUTONOMY_LEVEL_NAMES.get(int(autonomy_level)) if autonomy_level is not None else None,
            "gates": [gate.to_dict() for gate in gates],
        }
        return PolicyDecision(
            allowed=allowed,
            effective_risk=risk,
            gate_results=gates,
            required_approval=required_approval,
            blocked_reason=blocked_reason,
            audit=audit,
        )


policy_guard = PolicyGuard()
