"""
Safety Critic Agent — Phase 2 旁路审查者。

不参与推理，不调用 LLM。在 autonomous_remediation_agent 之后运行，
对前序 agent 的决策做一致性 / 安全性审查。

输出 AgentClaim:
- claim_type = "safety_review"
- status ∈ {"actionable", "hypothesis", "rejected"}
- output_payload.decision ∈ {"pass", "soft", "rejected"}
- output_payload.findings = [{rule_code, severity, message, detail}, ...]

严重度规则：
- critical / error → 硬性问题 → 整体 rejected → orchestrator 应把 Case 升级到 ESCALATED
- warning         → 软性顾虑 → 整体 hypothesis → 写入 plan.safety_checks 供人工审批参考
- 无 finding 或仅 info → actionable → 正常流程
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from models.agenticops import AgentType


_HARD_SEVERITIES = {"critical", "error"}
_SOFT_SEVERITIES = {"warning"}

# Confidence floor below which auto execution is unsafe (matches
# autonomous_remediation_agent.AUTO_EXECUTE_MIN_CONFIDENCE).
AUTO_CONFIDENCE_FLOOR = 0.7
# Priorities on which auto-execute must never be allowed.
NEVER_AUTO_PRIORITIES = {"P0", "P1"}


def _finding(rule_code: str, severity: str, message: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "rule_code": rule_code,
        "severity": severity,
        "message": message,
        "detail": detail or {},
    }


def _find_claim(prior_claims: List[Dict[str, Any]], claim_type: str) -> Optional[Dict[str, Any]]:
    return next((item for item in prior_claims if item.get("claim_type") == claim_type), None)


class SafetyCriticAgent(BaseOpsAgent):
    agent_type = AgentType.SAFETY_CRITIC
    agent_name = "Safety Critic Agent"

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        prior_claims = context.prior_claims or []
        findings: List[Dict[str, Any]] = []

        remediation = _find_claim(prior_claims, "remediation_strategy")
        insight = _find_claim(prior_claims, "root_cause_assessment")
        triage = _find_claim(prior_claims, "triage_assessment")

        # R001: evidence existence
        if not context.evidence_items:
            findings.append(
                _finding(
                    "R001",
                    "critical",
                    "Case 未收集到任何证据项，无法做安全研判",
                    {"evidence_count": 0},
                )
            )

        # R011: upstream agent failure (orchestrator emits agent_failure claim_type on exception)
        failed_claims = [item for item in prior_claims if item.get("claim_type") == "agent_failure"]
        if failed_claims:
            findings.append(
                _finding(
                    "R011",
                    "critical",
                    "上游 agent 执行失败，下游决策不可信",
                    {"failed_count": len(failed_claims)},
                )
            )

        # R002: presence of remediation strategy
        if remediation is None:
            findings.append(
                _finding(
                    "R002",
                    "error",
                    "未找到 remediation_strategy claim，Critic 跳过执行可行性审查",
                    {},
                )
            )

        # Extract remediation fields (safe defaults when missing)
        remediation_output = (remediation or {}).get("output_payload") or {}
        execution_mode = str(remediation_output.get("execution_mode") or "manual").lower()
        recommended_actions = remediation_output.get("recommended_actions") or []
        rollback_plan = remediation_output.get("rollback_plan") or []
        safety_checks = remediation_output.get("safety_checks") or {}
        observe_only = bool(safety_checks.get("observe_only", True))
        policy_pre_check = safety_checks.get("policy_pre_check") or []
        priority = str(safety_checks.get("priority") or "P3").upper()
        plan_confidence = float((remediation or {}).get("confidence") or 0.0)
        insight_confidence = float((insight or {}).get("confidence") or 0.0)

        # R003: recommended_actions must be non-empty when remediation present
        if remediation is not None and not recommended_actions:
            findings.append(
                _finding(
                    "R003",
                    "error",
                    "remediation_strategy 未给出任何 recommended_actions",
                    {},
                )
            )

        # R004: auto + observe_only is self-contradictory
        if execution_mode == "auto" and observe_only:
            findings.append(
                _finding(
                    "R004",
                    "critical",
                    "execution_mode=auto 与 observe_only=true 自相矛盾",
                    {"execution_mode": execution_mode, "observe_only": observe_only},
                )
            )

        # R005: auto with insufficient confidence
        if execution_mode == "auto" and plan_confidence < AUTO_CONFIDENCE_FLOOR:
            findings.append(
                _finding(
                    "R005",
                    "critical",
                    f"execution_mode=auto 但置信度 {plan_confidence:.2f} 低于自动执行下限 {AUTO_CONFIDENCE_FLOOR}",
                    {"confidence": plan_confidence, "floor": AUTO_CONFIDENCE_FLOOR},
                )
            )

        # R006: auto on critical priority
        if execution_mode == "auto" and priority in NEVER_AUTO_PRIORITIES:
            findings.append(
                _finding(
                    "R006",
                    "critical",
                    f"execution_mode=auto 不允许在 {priority} 优先级使用",
                    {"priority": priority},
                )
            )

        # R007: high-risk action with low insight confidence (soft)
        high_risk_actions = [
            item
            for item in policy_pre_check
            if isinstance(item, dict) and int(item.get("effective_risk") or 0) >= 3
        ]
        if high_risk_actions and insight_confidence < 0.5:
            findings.append(
                _finding(
                    "R007",
                    "warning",
                    "存在高风险动作但 insight 置信度偏低，建议人工复核",
                    {
                        "high_risk_tool_ids": [item.get("tool_id") for item in high_risk_actions],
                        "insight_confidence": insight_confidence,
                    },
                )
            )

        # R008: insight left unresolved gaps with low confidence (soft)
        insight_gaps = (insight or {}).get("gaps") or []
        if insight is not None and insight_gaps and insight_confidence < 0.6:
            findings.append(
                _finding(
                    "R008",
                    "warning",
                    f"insight 留下 {len(insight_gaps)} 项未解决 gap 且置信度 < 0.6",
                    {"gaps_sample": list(insight_gaps[:3]), "insight_confidence": insight_confidence},
                )
            )

        # R012 (Phase 4): hypothesis-tree shallow analysis.
        # Backward-compat: only fire when the insight claim actually carries a 'hypotheses'
        # field — older AgentRuns that pre-date Phase 4 lack it and shouldn't be flagged.
        if insight is not None:
            insight_payload = (insight or {}).get("output_payload") or {}
            if "hypotheses" in insight_payload:
                hypotheses = insight_payload.get("hypotheses") or []
                has_contradicting = any(
                    isinstance(h, dict) and (h.get("contradicting_evidence_ids") or [])
                    for h in hypotheses
                )
                if len(hypotheses) < 2 or not has_contradicting:
                    findings.append(
                        _finding(
                            "R012",
                            "warning",
                            "insight 假设树偏浅（候选 < 2 或无反证证据），建议补采证据后重跑",
                            {
                                "hypothesis_count": len(hypotheses),
                                "has_contradicting_evidence": has_contradicting,
                            },
                        )
                    )

        # R009: missing rollback plan (soft — Phase 1 plans may legitimately be advisory-only)
        if remediation is not None and not rollback_plan:
            findings.append(
                _finding(
                    "R009",
                    "warning",
                    "remediation_strategy 未提供 rollback_plan",
                    {},
                )
            )

        # R010: plan references an unregistered tool
        for item in policy_pre_check:
            if isinstance(item, dict) and item.get("blocked_reason") == "unregistered_tool":
                findings.append(
                    _finding(
                        "R010",
                        "error",
                        f"计划引用了未注册的工具 {item.get('tool_id')}",
                        {"tool_id": item.get("tool_id")},
                    )
                )

        # Aggregate
        hard_count = sum(1 for f in findings if f["severity"] in _HARD_SEVERITIES)
        soft_count = sum(1 for f in findings if f["severity"] in _SOFT_SEVERITIES)
        rule_codes = sorted({f["rule_code"] for f in findings})

        if hard_count > 0:
            decision = "rejected"
            status = "rejected"
            confidence_out = 0.95
            hard_codes = sorted({f["rule_code"] for f in findings if f["severity"] in _HARD_SEVERITIES})
            summary = f"Safety Critic 拒绝该计划：{hard_count} 项硬性问题（{', '.join(hard_codes)}）。"
        elif soft_count > 0:
            decision = "soft"
            status = "hypothesis"
            confidence_out = 0.6
            soft_codes = sorted({f["rule_code"] for f in findings if f["severity"] in _SOFT_SEVERITIES})
            summary = f"Safety Critic 提出 {soft_count} 项软性顾虑（{', '.join(soft_codes)}），建议人工复核后再执行。"
        else:
            decision = "pass"
            status = "actionable"
            confidence_out = 0.85
            summary = "Safety Critic 审查通过：未发现安全顾虑。"

        gaps = [f["message"] for f in findings if f["severity"] in _HARD_SEVERITIES]
        evidence_refs: List[Dict[str, Any]] = []
        for claim in (remediation, insight, triage):
            if claim and claim.get("id") is not None:
                evidence_refs.append({"type": "claim", "ref": str(claim.get("id"))})

        return AgentDecision(
            summary=summary,
            confidence=confidence_out,
            claim_type="safety_review",
            claim_text=summary,
            status=status,
            evidence_refs=evidence_refs,
            gaps=gaps,
            output_payload={
                "decision": decision,
                "hard_count": hard_count,
                "soft_count": soft_count,
                "findings": findings,
                "rule_codes": rule_codes,
                "reviewed_claim_ids": [str(c.get("id")) for c in (remediation, insight, triage) if c and c.get("id") is not None],
            },
            metadata={
                "decision": decision,
                "hard_count": hard_count,
                "soft_count": soft_count,
                "rule_codes": rule_codes,
            },
            stopped_reason="safety_critic_rejected" if decision == "rejected" else None,
        )


safety_critic_agent = SafetyCriticAgent()
