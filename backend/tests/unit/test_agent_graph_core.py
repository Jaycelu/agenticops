from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agents.diagnostic_critic_agent import diagnostic_critic_agent
from agents.schemas import AgentExecutionContext
from models.agent_graph import AgentTask
from orchestration.graph_contracts import EvidenceRequest, SupervisorDecision
from services.agent_task_service import agent_task_service
from services.case_state_service import ALLOWED, state_value
from tools.registry import tool_registry


def test_evidence_request_forbids_raw_shell_and_unknown_fields():
    with pytest.raises(ValidationError):
        EvidenceRequest.model_validate({
            "probe_id": "network.system_status",
            "target": {"netbox_device_id": 123},
            "parameters": {},
            "reason": "verify device state",
            "expected_evidence_type": "command_output",
            "command": "show running-config",
        })


def test_evidence_request_requires_stable_netbox_device_id():
    with pytest.raises(ValidationError):
        EvidenceRequest.model_validate({
            "probe_id": "network.system_status",
            "target": {"device_name": "router-1"},
            "parameters": {},
            "reason": "verify device state",
            "expected_evidence_type": "command_output",
        })


def test_only_explicit_read_only_tools_are_agent_selectable():
    selectable = {item.tool_id for item in tool_registry.agent_tools()}
    assert "network.system_status" in selectable
    assert "network.bgp.neighbor_detail" in selectable
    assert "api.request" not in selectable
    assert "script.run" not in selectable
    assert "ssh.config_change" not in selectable


def test_case_state_transition_table_covers_diagnostic_loop_and_blocks_shortcuts():
    assert "evidence_collecting" in ALLOWED["diagnosing"]
    assert "diagnosing" in ALLOWED["evidence_collecting"]
    assert "planning" in ALLOWED["hypothesis_review"]
    assert "executing" not in ALLOWED["diagnosing"]
    assert state_value("TRIAGED") == "triaged"


def test_agent_task_lifecycle_is_bounded_and_rejects_illegal_transition():
    task = AgentTask(task_type="agent", graph_node="diagnostic", status="ready", attempt_count=0)
    db = SimpleNamespace(flush=lambda: None)
    agent_task_service.transition(db, task, "running")
    assert task.status == "running"
    assert task.attempt_count == 1
    agent_task_service.transition(db, task, "completed", output={"ok": True})
    assert task.output_payload == {"ok": True}
    with pytest.raises(ValueError):
        agent_task_service.transition(db, task, "running")


def test_supervisor_contract_rejects_empty_non_wait_decision():
    with pytest.raises(ValidationError):
        SupervisorDecision.model_validate({"decision": "plan", "next_tasks": [], "reason": "missing work"})


@pytest.mark.asyncio
async def test_diagnostic_critic_rejects_missing_hypotheses():
    context = AgentExecutionContext(
        case_id=1,
        case_code="CASE-1",
        title="test",
        summary="",
        source_system="fake",
        source_payload={},
        normalized_payload={},
        runtime={"hypotheses": []},
    )
    decision = await diagnostic_critic_agent.run(context)
    assert decision.output_payload["decision"] == "reject"
    assert decision.cited_evidence_item_ids == []
