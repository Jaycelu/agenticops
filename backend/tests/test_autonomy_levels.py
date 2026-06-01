"""Phase 4.A — autonomy_level 推导 + PolicyGuard 按等级放行的单测。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from policies.guard import PolicyGuard
from policies.schemas import APPROVAL_THRESHOLD_BY_LEVEL, AUTONOMY_LEVEL_NAMES
from services.automation_settings_service import _derive_level
from tools.base import ToolRequest


class _FixedAutonomyGuard(PolicyGuard):
    """Test fixture: pin the autonomy_level to a known value."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self._fixed_level = int(level)

    def _autonomy_level(self, db):  # noqa: D401
        return self._fixed_level


# ---------------------------------------------------------------------------
# autonomy_level 推导（_derive_level）
# ---------------------------------------------------------------------------


def test_derive_level_explicit_value_wins_over_mode():
    assert _derive_level({"mode": "observe_only", "autonomy_level": 4}, env_observe_only_default=True) == 4


def test_derive_level_legacy_mode_migration():
    assert _derive_level({"mode": "observe_only"}, env_observe_only_default=True) == 1
    assert _derive_level({"mode": "auto"}, env_observe_only_default=True) == 2


def test_derive_level_invalid_value_falls_back_to_default():
    assert _derive_level({"autonomy_level": "bogus"}, env_observe_only_default=True) == 1
    assert _derive_level({"autonomy_level": 99}, env_observe_only_default=True) == 1
    assert _derive_level({"autonomy_level": -1}, env_observe_only_default=True) == 1


def test_derive_level_no_data_uses_env_default():
    assert _derive_level({}, env_observe_only_default=True) == 1
    assert _derive_level({}, env_observe_only_default=False) == 2
    assert _derive_level(None, env_observe_only_default=True) == 1


def test_approval_threshold_matrix():
    assert APPROVAL_THRESHOLD_BY_LEVEL[0] == 1
    assert APPROVAL_THRESHOLD_BY_LEVEL[1] == 1
    assert APPROVAL_THRESHOLD_BY_LEVEL[2] == 2
    assert APPROVAL_THRESHOLD_BY_LEVEL[3] == 3
    assert APPROVAL_THRESHOLD_BY_LEVEL[4] == 4
    assert APPROVAL_THRESHOLD_BY_LEVEL[5] == 4


def test_autonomy_names_complete():
    assert set(AUTONOMY_LEVEL_NAMES.keys()) == {0, 1, 2, 3, 4, 5}


# ---------------------------------------------------------------------------
# L0 OBSERVE_ONLY — 阻断一切，包括 notification
# ---------------------------------------------------------------------------


def test_l0_blocks_notification():
    decision = _FixedAutonomyGuard(0).check(
        ToolRequest(tool_id="notify.dingtalk", params={"message": "x"}, mode="execute")
    )
    assert not decision.allowed
    assert decision.blocked_reason == "autonomy_block_all"


def test_l0_audit_records_level_and_name():
    decision = _FixedAutonomyGuard(0).check(
        ToolRequest(tool_id="notify.dingtalk", params={"message": "x"}, mode="execute")
    )
    assert decision.audit["autonomy_level"] == 0
    assert decision.audit["autonomy_level_name"] == "observe_only"


# ---------------------------------------------------------------------------
# L1 RECOMMEND — notification 开口；mutation 阻断
# ---------------------------------------------------------------------------


def test_l1_allows_notification():
    decision = _FixedAutonomyGuard(1).check(
        ToolRequest(tool_id="notify.dingtalk", params={"message": "x"}, mode="execute")
    )
    assert decision.allowed
    assert decision.audit["autonomy_level"] == 1


def test_l1_blocks_mutating_api_even_when_plan_approved():
    """L1 仍保持原 observe_only 行为：核心区分点是 mutation 在 L1 被阻断、L2 放行。"""
    plan = MagicMock()
    plan.approval_status = "approved"
    request = ToolRequest(
        tool_id="api.request",
        params={"url": "http://example.local/api/x", "method": "POST"},
        mode="execute",
    )
    decision = _FixedAutonomyGuard(1).check(request, plan=plan)
    assert not decision.allowed
    # L1 approval threshold = 1, api.request 自带 requires_approval -> approval 先 fire
    assert decision.blocked_reason in {"approval_required", "observe_only_blocked"}


# ---------------------------------------------------------------------------
# L2 ASSISTED — 默认 auto。risk >= 2 才需审批
# ---------------------------------------------------------------------------


def test_l2_audit_records_assisted():
    decision = _FixedAutonomyGuard(2).check(
        ToolRequest(tool_id="notify.dingtalk", params={"message": "x"}, mode="execute")
    )
    assert decision.audit["autonomy_level"] == 2
    assert decision.audit["autonomy_level_name"] == "assisted"


def test_l2_blocks_script_without_approval():
    """script.run 自带 requires_approval=True，所以任何 level 没 plan 都该挡。"""
    decision = _FixedAutonomyGuard(2).check(
        ToolRequest(
            tool_id="script.run",
            params={"script_path": "x.sh"},
            mode="execute",
        )
    )
    assert not decision.allowed
    assert decision.blocked_reason == "approval_required"


# ---------------------------------------------------------------------------
# L4 AUTONOMOUS — notification 与 L1 一样开放；audit 字段反映 autonomous
# ---------------------------------------------------------------------------


def test_l4_allows_notification_and_audit_name():
    decision = _FixedAutonomyGuard(4).check(
        ToolRequest(tool_id="notify.dingtalk", params={"message": "x"}, mode="execute")
    )
    assert decision.allowed
    assert decision.audit["autonomy_level"] == 4
    assert decision.audit["autonomy_level_name"] == "autonomous"


def test_l4_blocks_destructive_via_blocked_patterns_even_without_observe_only():
    """blocked_patterns 把 ssh.show_command 的 reboot 升到 R>=3；L4 approval 阈值 4，
    但 spec.requires_approval=False 且 risk=3<4 时不需审批；然而 ssh.show_command 的 executable=False
    会在 execution gate 兜底挡住——证明多道门叠加保护。"""
    request = ToolRequest(
        tool_id="ssh.show_command",
        params={"commands": ["reboot"]},
        mode="observe",
    )
    decision = _FixedAutonomyGuard(4).check(request)
    assert not decision.allowed
    # The exact reason depends on which gate fires first; both are acceptable safety outcomes.
    assert decision.blocked_reason in {"approval_required", "tool_not_executable"}


# ---------------------------------------------------------------------------
# 横向：同一 tool 在 L0..L4 上的 allowed 状态矩阵
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "level, expected_allowed",
    [
        (0, False),  # L0 blocks notifications
        (1, True),   # L1 allows notifications (carve-out)
        (2, True),
        (3, True),
        (4, True),
        (5, True),
    ],
)
def test_notification_level_matrix(level, expected_allowed):
    decision = _FixedAutonomyGuard(level).check(
        ToolRequest(tool_id="notify.dingtalk", params={"message": "x"}, mode="execute")
    )
    assert decision.allowed is expected_allowed
