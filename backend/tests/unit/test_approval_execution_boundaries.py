from __future__ import annotations

import pytest

from approvals.service import canonical_plan_payload, plan_payload_hash
from models.agenticops import CaseRecord, RemediationPlan
from services.execution_service import ExecutionService
from services.ssh_mutation_executor import ssh_mutation_executor
from tools.registry import tool_registry


pytestmark = pytest.mark.unit


def plan() -> RemediationPlan:
    return RemediationPlan(
        id=11,
        case_id=7,
        plan_code="PLAN-11",
        execution_mode="assisted",
        risk_level="high",
        summary="Change interface state",
        plan_payload={"recommended_actions": [{"tool_id": "ssh.config_change", "commands": ["interface Gi0/1"]}]},
        rollback_payload={"recommended_actions": [{"tool_id": "ssh.config_change", "commands": ["default interface Gi0/1"]}]},
        safety_checks={"change_window": "night"},
    )


def test_frozen_plan_hash_changes_for_any_executable_field() -> None:
    item = plan()
    original = plan_payload_hash(canonical_plan_payload(item))

    item.plan_payload = {"recommended_actions": [{"tool_id": "ssh.config_change", "commands": ["reload"]}]}
    assert plan_payload_hash(canonical_plan_payload(item)) != original


def test_tool_capability_is_registry_owned_not_agent_mode() -> None:
    item = plan()
    case = CaseRecord(id=7, case_code="CASE-7", title="Interface down", case_metadata={})
    service = ExecutionService()

    mutation = service._build_tool_request(
        {"tool_id": "ssh.config_change", "mode": "observe", "commands": ["shutdown"]},
        case=case,
        plan=item,
        triggered_by="executor",
    )
    read_only = service._build_tool_request(
        {"tool_id": "ssh.show_command", "mode": "execute", "commands": ["show version"]},
        case=case,
        plan=item,
        triggered_by="executor",
    )

    assert mutation.mode == "execute"
    assert read_only.mode == "observe"
    assert tool_registry.get("ssh.config_change").capability == "mutation"
    assert tool_registry.get("ssh.show_command").capability == "read_only"


def test_all_mutation_capabilities_require_approval() -> None:
    mutations = [item for item in tool_registry.list() if item.capability == "mutation"]

    assert mutations
    assert all(item.requires_approval for item in mutations)


def test_ssh_mutation_executor_requires_scoped_target_and_rejects_inline_secrets() -> None:
    base = {
        "commands": ["interface GigabitEthernet0/1", "shutdown"],
        "credential_id": 3,
        "netbox_device_id": 9,
    }

    assert ssh_mutation_executor.validate_config(base)
    assert not ssh_mutation_executor.validate_config({**base, "commands": ["password leaked"]})
    assert not ssh_mutation_executor.validate_config({**base, "commands": ["shutdown\nreload"]})
    assert not ssh_mutation_executor.validate_config({**base, "credential_id": None})
