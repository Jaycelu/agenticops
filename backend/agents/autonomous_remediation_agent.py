from typing import Any, Dict, List, Optional

from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from config.settings import settings
from models.agenticops import AgentType
from policies.guard import policy_guard
from policies.schemas import AUTONOMY_LEVEL_NAMES, AutonomyLevel
from services.automation_settings_service import automation_settings_service
from services.remediation_recommendation_service import remediation_recommendation_service
from tools.base import ToolRequest
from tools.registry import tool_registry


# Auto-execute confidence floor. Lower than the previous hard-coded 0.85 because
# the heavy gating is now policy-driven (PolicyGuard); confidence is one input,
# not the only gate. Critical incidents (P0/P1) never auto-execute.
AUTO_EXECUTE_MIN_CONFIDENCE = 0.7
AUTO_EXECUTE_ALLOWED_PRIORITIES = {"P2", "P3", "P4"}
# Auto execution requires autonomy_level >= ASSISTED (Phase 4).
AUTO_EXECUTE_MIN_AUTONOMY = int(AutonomyLevel.ASSISTED)


class AutonomousRemediationAgent(BaseOpsAgent):
    agent_type = AgentType.REMEDIATION
    agent_name = "Autonomous Remediation Agent"

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        prior_claims = context.prior_claims or []
        insight_claim = next((item for item in prior_claims if item.get("claim_type") == "root_cause_assessment"), {})
        triage_claim = next((item for item in prior_claims if item.get("claim_type") == "triage_assessment"), {})

        root_cause = ((insight_claim.get("output_payload") or {}).get("root_cause")) or "unknown"
        impact_scope = ((insight_claim.get("output_payload") or {}).get("impact_scope")) or "single_device"
        signal_family = str(root_cause).split(":")[0] if ":" in str(root_cause) else root_cause
        priority = str(((triage_claim.get("metadata") or {}).get("priority")) or "P3").upper()
        confidence = float(insight_claim.get("confidence") or triage_claim.get("confidence") or 0.4)
        cross_source = bool(context.runtime.get("log_summary")) and bool(context.runtime.get("zabbix_alerts"))
        recommendations: List[str] = list(((insight_claim.get("output_payload") or {}).get("recommendations")) or [])
        recommended_actions = remediation_recommendation_service.build_actions(
            root_cause=root_cause,
            signal_family=signal_family,
            impact_scope=impact_scope,
            priority=priority,
            cross_source=cross_source,
        )
        policy_audit = dict(getattr(remediation_recommendation_service, "last_policy_audit", {}) or {})

        if not recommendations:
            recommendations = [item["title"] for item in recommended_actions[:3]]

        # Phase 4: 从 DB 读 autonomy_level（兼容老的 observe_only 字段）。
        autonomy_level, is_observe_only, automation_mode = self._resolve_autonomy()

        # 真正的 PolicyGuard 预检：对每个挂了 tool_id 的 action 跑一遍 5 道门，
        # 用结果反推 execution_mode / approval_status。
        # 没挂 tool_id 的 advisory action 不参与执行可行性判断（属于过程性建议）。
        pre_check = self._policy_pre_check(recommended_actions, context=context)

        executable_action_seen = pre_check["executable_action_seen"]
        needs_approval = pre_check["needs_approval"]
        any_runtime_blocked = pre_check["any_runtime_blocked"]

        auto_eligible = (
            executable_action_seen
            and not needs_approval
            and not any_runtime_blocked
            and autonomy_level >= AUTO_EXECUTE_MIN_AUTONOMY
            and confidence >= AUTO_EXECUTE_MIN_CONFIDENCE
            and priority in AUTO_EXECUTE_ALLOWED_PRIORITIES
        )

        if auto_eligible:
            execution_mode = "auto"
            approval_status = "not_required"
        elif needs_approval:
            execution_mode = "manual"
            approval_status = "required"
        else:
            # 没有可执行 tool / 在 observe-only / 置信度不足 / 优先级过高 —— 一律保守为人工。
            execution_mode = "manual"
            approval_status = "required"

        summary = (
            f"已生成修复计划草案，根因候选为 {root_cause}，执行模式 {execution_mode}，"
            f"autonomy=L{autonomy_level}({AUTONOMY_LEVEL_NAMES.get(autonomy_level)})，"
            f"policy_pre_check={len(pre_check['decisions'])} 项。"
        )

        return AgentDecision(
            summary=summary,
            confidence=min(0.9, max(0.45, confidence)),
            claim_type="remediation_strategy",
            claim_text=summary,
            status="actionable",
            evidence_refs=[{"type": "claim", "ref": item.get("id", "runtime")} for item in prior_claims[-3:]],
            gaps=[],
            output_payload={
                "root_cause": root_cause,
                "impact_scope": impact_scope,
                "execution_mode": execution_mode,
                "approval_status": approval_status,
                "recommendations": recommendations,
                "recommended_actions": recommended_actions,
                "safety_checks": {
                    "autonomy_level": autonomy_level,
                    "autonomy_level_name": AUTONOMY_LEVEL_NAMES.get(autonomy_level),
                    "automation_mode": automation_mode,
                    "observe_only": is_observe_only,
                    "auto_min_autonomy": AUTO_EXECUTE_MIN_AUTONOMY,
                    "requires_approval": approval_status == "required",
                    "confidence": confidence,
                    "confidence_floor": AUTO_EXECUTE_MIN_CONFIDENCE,
                    "priority": priority,
                    "executable_action_seen": executable_action_seen,
                    "policy_pre_check": pre_check["decisions"],
                    "policy_guard": "enforced_at_execution",
                    "execution_closed_loop": True,
                },
                "rollback_plan": [
                    "记录变更前状态",
                    "若执行验证失败，回退到变更前配置",
                    "自动记录审计并转人工确认",
                ],
                "policy_audit": policy_audit,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_autonomy(self) -> tuple[int, bool, str]:
        """
        Read (autonomy_level, is_observe_only, mode) from DB; fall back to env default on error.

        Returned mode is the legacy 'observe_only' | 'auto' value, kept for trace readability.
        """
        try:
            from database import get_db

            db = next(get_db())
            try:
                data = automation_settings_service.get_automation_mode(db)
                level = int(data.get("autonomy_level") or AutonomyLevel.RECOMMEND)
                return level, bool(data.get("is_observe_only", True)), str(data.get("mode") or "observe_only")
            finally:
                db.close()
        except Exception:
            fallback_level = int(AutonomyLevel.RECOMMEND) if settings.automation_observe_only else int(AutonomyLevel.ASSISTED)
            fallback_mode = "observe_only" if settings.automation_observe_only else "auto"
            return fallback_level, bool(settings.automation_observe_only), fallback_mode

    def _build_target(self, context: AgentExecutionContext) -> Dict[str, Any]:
        device_runtime = context.runtime.get("device") or {}
        return {
            "site_id": context.site_id,
            "netbox_device_id": context.netbox_device_id,
            "device_ip": context.device_ip,
            "host": context.host,
            "role": device_runtime.get("role"),
            "device_role": device_runtime.get("role"),
            "tags": device_runtime.get("tags") or [],
        }

    def _policy_pre_check(
        self,
        actions: List[Dict[str, Any]],
        *,
        context: AgentExecutionContext,
    ) -> Dict[str, Any]:
        """
        Run PolicyGuard.check on every action that carries a tool_id.

        Pre-check semantics:
        - db=None  -> circuit breaker check is skipped (runtime concern, evaluated again later);
                       observe-only check falls back to env default.
        - plan=None -> approval gate fails when the tool requires approval; that's exactly
                        what we want to detect at planning time.

        Actions without tool_id are advisory; they are recorded but do not affect
        executable_action_seen.
        """
        decisions: List[Dict[str, Any]] = []
        executable_action_seen = False
        needs_approval = False
        any_runtime_blocked = False
        target = self._build_target(context)

        for action in actions:
            tool_id: Optional[str] = action.get("tool_id")
            if not tool_id:
                decisions.append(
                    {
                        "tool_id": None,
                        "action_type": action.get("action_type"),
                        "title": action.get("title"),
                        "kind": "advisory",
                    }
                )
                continue

            spec = tool_registry.get(tool_id)
            if spec is None:
                decisions.append(
                    {
                        "tool_id": tool_id,
                        "allowed": False,
                        "blocked_reason": "unregistered_tool",
                    }
                )
                continue
            if not spec.executable:
                decisions.append(
                    {
                        "tool_id": tool_id,
                        "allowed": False,
                        "blocked_reason": "tool_not_executable",
                        "executable": False,
                    }
                )
                continue

            executable_action_seen = True
            mode = str(action.get("tool_mode") or action.get("mode") or "execute")
            request = ToolRequest(
                tool_id=tool_id,
                params=dict(action.get("params") or {}),
                target=target,
                mode=mode,
                action=action,
                requested_by="agent.autonomous_remediation",
                case_id=context.case_id,
            )
            decision = policy_guard.check(request, plan=None, db=None)

            decisions.append(
                {
                    "tool_id": tool_id,
                    "allowed": decision.allowed,
                    "effective_risk": decision.effective_risk,
                    "blocked_reason": decision.blocked_reason,
                    "required_approval": decision.required_approval,
                }
            )

            if decision.required_approval:
                needs_approval = True
            # approval_required at this stage is expected (no plan yet) and does not
            # signify a runtime obstacle — only treat *other* blocks as runtime issues.
            if (
                not decision.allowed
                and decision.blocked_reason
                and decision.blocked_reason != "approval_required"
            ):
                any_runtime_blocked = True

        return {
            "decisions": decisions,
            "executable_action_seen": executable_action_seen,
            "needs_approval": needs_approval,
            "any_runtime_blocked": any_runtime_blocked,
        }


autonomous_remediation_agent = AutonomousRemediationAgent()
