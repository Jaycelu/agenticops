"""SafetyCriticAgent 单元测试（Phase 2）。

纯函数测试：构造 mock AgentExecutionContext 与 prior_claims，断言
critic 的 status / decision / rule_codes / hard_count / soft_count。

不依赖 DB / LLM / fastapi。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from agents.safety_critic_agent import safety_critic_agent
from agents.schemas import AgentExecutionContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _ctx(
    *,
    evidence_items: Optional[List[Dict[str, Any]]] = None,
    prior_claims: Optional[List[Dict[str, Any]]] = None,
) -> AgentExecutionContext:
    return AgentExecutionContext(
        case_id=1,
        case_code="CASE-T1",
        title="test",
        summary="",
        source_system="ELK",
        source_payload={},
        normalized_payload={},
        evidence_items=list(evidence_items) if evidence_items is not None else [{"id": 1, "evidence_type": "alert"}],
        prior_claims=list(prior_claims) if prior_claims is not None else [],
    )


def _claim(
    *,
    claim_id: int,
    claim_type: str,
    confidence: float = 0.7,
    gaps: Optional[List[str]] = None,
    output_payload: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a prior_claims dict matching engines/case_orchestrator._append_agent shape."""
    return {
        "id": claim_id,
        "agent_type": claim_type,
        "claim_type": claim_type,
        "confidence": confidence,
        "gaps": list(gaps or []),
        "output_payload": dict(output_payload or {}),
        "metadata": dict(metadata or {}),
    }


def _triage(**overrides) -> Dict[str, Any]:
    return _claim(
        claim_id=overrides.get("claim_id", 10),
        claim_type="triage_assessment",
        confidence=overrides.get("confidence", 0.82),
        output_payload=overrides.get("output_payload", {"classification": "log_burst", "priority": "P3"}),
        metadata=overrides.get("metadata", {"priority": "P3"}),
    )


def _insight(
    *,
    confidence: float = 0.7,
    gaps: Optional[List[str]] = None,
    output_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _claim(
        claim_id=20,
        claim_type="root_cause_assessment",
        confidence=confidence,
        gaps=gaps or [],
        output_payload=output_payload or {"root_cause": "x", "impact_scope": "single_device"},
    )


def _remediation(
    *,
    confidence: float = 0.75,
    execution_mode: str = "manual",
    observe_only: bool = True,
    priority: str = "P3",
    recommended_actions: Optional[List[Dict[str, Any]]] = None,
    rollback_plan: Optional[List[str]] = None,
    policy_pre_check: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if recommended_actions is None:
        recommended_actions = [{"title": "advisory review", "action_type": "cross_source_review"}]
    if rollback_plan is None:
        rollback_plan = ["记录变更前状态", "回退到变更前配置"]
    safety_checks = {
        "observe_only": observe_only,
        "priority": priority,
        "policy_pre_check": list(policy_pre_check or []),
    }
    return _claim(
        claim_id=30,
        claim_type="remediation_strategy",
        confidence=confidence,
        output_payload={
            "root_cause": "x",
            "execution_mode": execution_mode,
            "approval_status": "required" if execution_mode == "manual" else "not_required",
            "recommended_actions": recommended_actions,
            "rollback_plan": rollback_plan,
            "safety_checks": safety_checks,
        },
    )


# ---------------------------------------------------------------------------
# Pass case (no findings)
# ---------------------------------------------------------------------------

def test_clean_plan_passes():
    ctx = _ctx(prior_claims=[_triage(), _insight(), _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "actionable"
    assert decision.output_payload["decision"] == "pass"
    assert decision.output_payload["hard_count"] == 0
    assert decision.output_payload["soft_count"] == 0
    assert decision.output_payload["rule_codes"] == []


# ---------------------------------------------------------------------------
# Hard rejections
# ---------------------------------------------------------------------------

def test_no_evidence_rejected_R001():
    ctx = _ctx(evidence_items=[], prior_claims=[_triage(), _insight(), _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R001" in decision.output_payload["rule_codes"]


def test_no_remediation_rejected_R002():
    ctx = _ctx(prior_claims=[_triage(), _insight()])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R002" in decision.output_payload["rule_codes"]


def test_no_recommended_actions_rejected_R003():
    rem = _remediation(recommended_actions=[])
    ctx = _ctx(prior_claims=[_triage(), _insight(), rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R003" in decision.output_payload["rule_codes"]


def test_auto_in_observe_only_rejected_R004():
    rem = _remediation(execution_mode="auto", observe_only=True)
    ctx = _ctx(prior_claims=[_triage(), _insight(confidence=0.9), rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R004" in decision.output_payload["rule_codes"]


def test_auto_with_low_confidence_rejected_R005():
    rem = _remediation(execution_mode="auto", observe_only=False, confidence=0.5)
    ctx = _ctx(prior_claims=[_triage(), _insight(confidence=0.5), rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R005" in decision.output_payload["rule_codes"]


def test_auto_on_critical_priority_rejected_R006():
    rem = _remediation(execution_mode="auto", observe_only=False, priority="P1", confidence=0.85)
    ctx = _ctx(prior_claims=[_triage(), _insight(), rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R006" in decision.output_payload["rule_codes"]


def test_unregistered_tool_rejected_R010():
    rem = _remediation(
        policy_pre_check=[{"tool_id": "missing.tool", "allowed": False, "blocked_reason": "unregistered_tool"}],
    )
    ctx = _ctx(prior_claims=[_triage(), _insight(), rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R010" in decision.output_payload["rule_codes"]


def test_upstream_agent_failure_rejected_R011():
    failure = _claim(claim_id=999, claim_type="agent_failure", confidence=0.0)
    ctx = _ctx(prior_claims=[_triage(), failure, _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert "R011" in decision.output_payload["rule_codes"]


# ---------------------------------------------------------------------------
# Soft warnings
# ---------------------------------------------------------------------------

def test_high_risk_low_insight_confidence_soft_R007():
    insight = _insight(confidence=0.3)
    rem = _remediation(
        policy_pre_check=[
            {"tool_id": "ssh.config_change", "allowed": False, "effective_risk": 3, "blocked_reason": "approval_required"}
        ]
    )
    ctx = _ctx(prior_claims=[_triage(), insight, rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "hypothesis"
    assert "R007" in decision.output_payload["rule_codes"]
    assert decision.output_payload["hard_count"] == 0
    assert decision.output_payload["soft_count"] >= 1


def test_unresolved_insight_gaps_soft_R008():
    insight = _insight(confidence=0.4, gaps=["缺少拓扑上下文", "Zabbix 详情缺失"])
    ctx = _ctx(prior_claims=[_triage(), insight, _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "hypothesis"
    assert "R008" in decision.output_payload["rule_codes"]


def test_missing_rollback_soft_R009():
    rem = _remediation(rollback_plan=[])
    ctx = _ctx(prior_claims=[_triage(), _insight(), rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "hypothesis"
    assert "R009" in decision.output_payload["rule_codes"]


# ---------------------------------------------------------------------------
# Aggregation: hard always wins over soft
# ---------------------------------------------------------------------------

def test_hard_finding_outranks_soft():
    # R004 critical (auto + observe_only) + R009 warning (no rollback) -> rejected
    rem = _remediation(execution_mode="auto", observe_only=True, rollback_plan=[])
    ctx = _ctx(prior_claims=[_triage(), _insight(), rem])
    decision = _run(safety_critic_agent.run(ctx))
    assert decision.status == "rejected"
    assert decision.output_payload["hard_count"] >= 1
    assert decision.output_payload["soft_count"] >= 1
    assert "R004" in decision.output_payload["rule_codes"]
    assert "R009" in decision.output_payload["rule_codes"]


def test_stopped_reason_only_on_rejection():
    # Pass case: no stopped_reason
    pass_decision = _run(safety_critic_agent.run(_ctx(prior_claims=[_triage(), _insight(), _remediation()])))
    assert pass_decision.stopped_reason is None
    # Rejected case: stopped_reason set
    reject_ctx = _ctx(evidence_items=[], prior_claims=[_triage(), _insight(), _remediation()])
    reject_decision = _run(safety_critic_agent.run(reject_ctx))
    assert reject_decision.stopped_reason == "safety_critic_rejected"


# ---------------------------------------------------------------------------
# Phase 4.A — R012 hypothesis-tree quality
# ---------------------------------------------------------------------------


def _insight_with_hypotheses(hypotheses):
    return _insight(output_payload={"root_cause": "x", "hypotheses": hypotheses})


def test_R012_fires_on_single_hypothesis():
    insight = _insight_with_hypotheses([
        {"id": "h1", "cause": "only_one", "confidence": 0.6,
         "supporting_evidence_ids": [1], "contradicting_evidence_ids": [2]},
    ])
    ctx = _ctx(prior_claims=[_triage(), insight, _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert "R012" in decision.output_payload["rule_codes"]
    assert decision.status == "hypothesis"  # soft warning


def test_R012_fires_when_no_contradicting_evidence():
    insight = _insight_with_hypotheses([
        {"id": "h1", "cause": "a", "confidence": 0.6, "supporting_evidence_ids": [1], "contradicting_evidence_ids": []},
        {"id": "h2", "cause": "b", "confidence": 0.4, "supporting_evidence_ids": [2], "contradicting_evidence_ids": []},
    ])
    ctx = _ctx(prior_claims=[_triage(), insight, _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert "R012" in decision.output_payload["rule_codes"]


def test_R012_silent_when_tree_is_deep_and_has_contradicting():
    insight = _insight_with_hypotheses([
        {"id": "h1", "cause": "a", "confidence": 0.7,
         "supporting_evidence_ids": [1], "contradicting_evidence_ids": [3]},
        {"id": "h2", "cause": "b", "confidence": 0.4,
         "supporting_evidence_ids": [2], "contradicting_evidence_ids": []},
    ])
    ctx = _ctx(prior_claims=[_triage(), insight, _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert "R012" not in decision.output_payload["rule_codes"]


def test_R012_fires_on_empty_hypotheses_list():
    insight = _insight_with_hypotheses([])
    ctx = _ctx(prior_claims=[_triage(), insight, _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert "R012" in decision.output_payload["rule_codes"]


def test_R012_silent_when_hypotheses_key_absent_legacy_insight():
    """Legacy AgentClaims (pre-Phase 4) lack 'hypotheses' — must not flag."""
    legacy_insight = _insight(output_payload={"root_cause": "x", "impact_scope": "single_device"})
    ctx = _ctx(prior_claims=[_triage(), legacy_insight, _remediation()])
    decision = _run(safety_critic_agent.run(ctx))
    assert "R012" not in decision.output_payload["rule_codes"]
    # Should still be a clean pass (no other findings).
    assert decision.status == "actionable"
