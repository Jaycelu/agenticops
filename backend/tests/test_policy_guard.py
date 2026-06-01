from unittest.mock import MagicMock

from policies.guard import PolicyGuard
from tools.base import ToolRequest


def test_policy_guard_rejects_unregistered_tool():
    decision = PolicyGuard().check(ToolRequest(tool_id="missing.tool"))

    assert not decision.allowed
    assert decision.blocked_reason == "unregistered_tool"
    assert decision.gate_results[0].gate == "schema"


def test_policy_guard_escalates_blacklisted_readonly_command():
    request = ToolRequest(
        tool_id="ssh.show_command",
        params={"commands": ["reboot"]},
        target={"device_ip": "10.0.0.1"},
        mode="observe",
    )

    decision = PolicyGuard().check(request)

    assert not decision.allowed
    assert decision.effective_risk >= 3
    assert decision.blocked_reason in {"approval_required", "observe_only_blocked"}
    risk_gate = next(item for item in decision.gate_results if item.gate == "risk")
    assert risk_gate.detail["blocked_patterns"]


def test_policy_guard_requires_approval_for_high_risk_tool():
    request = ToolRequest(
        tool_id="script.run",
        params={"script_path": "fix_interface.sh"},
        target={"device_ip": "10.0.0.1"},
        mode="execute",
    )
    plan = MagicMock()
    plan.approval_status = "required"

    decision = PolicyGuard().check(request, plan=plan)

    assert not decision.allowed
    assert decision.required_approval
    assert decision.blocked_reason == "approval_required"


def test_policy_guard_allows_notification_without_approval():
    request = ToolRequest(
        tool_id="notify.dingtalk",
        params={"message": "case update"},
        target={"device_ip": "10.0.0.1"},
        mode="execute",
    )

    decision = PolicyGuard().check(request)

    assert decision.allowed
    assert decision.effective_risk == 0
    assert not decision.required_approval
