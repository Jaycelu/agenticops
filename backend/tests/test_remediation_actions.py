"""Phase 1.5 — build_actions tool_id 挂载测试。

build_actions 读取真实 storage/remediation_policy.v1.json；不依赖 DB / LLM。
"""
from __future__ import annotations

from services.remediation_recommendation_service import (
    RemediationRecommendationService,
    remediation_recommendation_service,
)


def test_build_actions_every_action_has_tool_id():
    actions = remediation_recommendation_service.build_actions(
        root_cause="link_quality_degrade",
        signal_family="crc",
        impact_scope="device_scope",
        priority="P2",
    )
    assert actions
    for action in actions:
        assert action.get("tool_id"), f"action missing tool_id: {action}"


def test_build_actions_advisory_actions_map_to_manual_review():
    # All current policy rules emit mode=manual_check advisory actions.
    actions = remediation_recommendation_service.build_actions(
        root_cause="unknown",
        signal_family="generic",
        impact_scope="device_scope",
        priority="P3",
    )
    assert actions
    assert all(action["tool_id"] == "manual.review" for action in actions)


def test_infer_tool_id_executable_modes():
    infer = RemediationRecommendationService._infer_tool_id
    assert infer({"mode": "notify"}) == "notify.dingtalk"
    assert infer({"action_type": "notification"}) == "notify.dingtalk"
    assert infer({"action_type": "api_request"}) == "api.request"
    assert infer({"mode": "script"}) == "script.run"


def test_infer_tool_id_advisory_default_and_passthrough():
    infer = RemediationRecommendationService._infer_tool_id
    # advisory action types default to manual.review
    assert infer({"action_type": "cross_source_review", "mode": "manual_check"}) == "manual.review"
    assert infer({"action_type": "ticket_only", "mode": "manual_check"}) == "manual.review"
    # explicit tool_id is passed through untouched
    assert infer({"tool_id": "custom.tool", "mode": "manual_check"}) == "custom.tool"
