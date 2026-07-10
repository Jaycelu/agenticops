from __future__ import annotations

import pytest

from tools.registry import tool_registry


pytestmark = pytest.mark.unit


def test_unknown_tool_is_not_registered() -> None:
    assert tool_registry.get("unknown.tool") is None


def test_required_tool_parameters_are_enforced() -> None:
    spec = tool_registry.get("notify.dingtalk")
    assert spec is not None

    valid, errors = tool_registry.validate_params(spec, {})

    assert valid is False
    assert errors == ["missing_required:message"]


def test_read_only_ssh_commands_must_match_allowlist() -> None:
    spec = tool_registry.get("ssh.show_command")
    assert spec is not None

    assert tool_registry.commands_match_allowlist(
        spec,
        {"commands": ["show interfaces status", "show logging"]},
    )
    assert not tool_registry.commands_match_allowlist(
        spec,
        {"commands": ["configure terminal"]},
    )


def test_blocked_command_patterns_are_detected() -> None:
    spec = tool_registry.get("ssh.show_command")
    assert spec is not None

    hits = tool_registry.find_blocked_patterns(
        spec,
        {"commands": ["display interface", "reboot"]},
    )

    assert hits
