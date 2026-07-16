from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.diagnostic_critic_agent import diagnostic_critic_agent
from agents.insight_analysis_agent import insight_analysis_agent
from agents.schemas import AgentExecutionContext


pytestmark = pytest.mark.unit


class FakeEvidenceAdapter:
    """Controlled scenario evidence; never connects to an external system."""

    @staticmethod
    def context(name: str) -> AgentExecutionContext:
        now = datetime.now(timezone.utc)
        rows = {
            "bgp_neighbor_down": [
                {"id": 1, "evidence_type": "command_output", "source_system": "fake_probe", "summary": "BGP Idle", "collected_at": now},
            ],
            "interface_down": [
                {"id": 2, "evidence_type": "command_output", "source_system": "fake_probe", "summary": "Gi0/1 line protocol down", "collected_at": now},
            ],
            "zabbix_false_positive": [
                {"id": 3, "evidence_type": "alert", "source_system": "fake_zabbix", "summary": "interface down alert", "collected_at": now},
                {"id": 4, "evidence_type": "command_output", "source_system": "fake_probe", "summary": "interface up", "collected_at": now},
            ],
            "elk_log_storm": [
                {"id": 5, "evidence_type": "log", "source_system": "fake_elk", "summary": "repeated adjacency logs", "collected_at": now},
            ],
            "multi_source_conflict": [
                {"id": 6, "evidence_type": "metric", "source_system": "fake_zabbix", "summary": "loss 100%", "collected_at": now},
                {"id": 7, "evidence_type": "command_output", "source_system": "fake_probe", "summary": "traffic forwarding", "collected_at": now},
            ],
        }[name]
        ids = [item["id"] for item in rows]
        contradicting = ids[-1:] if name in {"zabbix_false_positive", "multi_source_conflict"} else []
        return AgentExecutionContext(
            case_id=1, case_code=f"CASE-{name}", title=name, summary="", source_system="fake",
            source_payload={}, normalized_payload={}, evidence_items=rows,
            runtime={"hypotheses": [{
                "hypothesis_code": "h1", "cause_code": name, "cause": name,
                "confidence": 0.9, "supporting_evidence_ids": ids[:1],
                "contradicting_evidence_ids": contradicting,
            }]},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("bgp_neighbor_down", "accept"),
        ("interface_down", "accept"),
        ("zabbix_false_positive", "revise"),
        ("elk_log_storm", "revise"),
        ("multi_source_conflict", "revise"),
    ],
)
async def test_critic_scenario_arbitration(scenario: str, expected: str):
    decision = await diagnostic_critic_agent.run(FakeEvidenceAdapter.context(scenario))
    assert decision.output_payload["decision"] == expected
    if expected != "accept":
        assert decision.output_payload["findings"]


@pytest.mark.asyncio
async def test_netbox_missing_does_not_invent_probe_target(monkeypatch):
    async def low_confidence(_payload):
        return {
            "root_cause": "unknown", "confidence": 0.2, "summary": "target missing",
            "hypotheses": [{
                "id": "h1", "cause_code": "unknown", "cause": "unknown", "confidence": 0.2,
                "supporting_evidence_ids": [8], "contradicting_evidence_ids": [],
                "missing_evidence": ["NetBox device"], "next_probe_requests": [], "status": "proposed",
            }],
        }

    monkeypatch.setattr(insight_analysis_agent, "_infer_with_llm", low_confidence)
    context = AgentExecutionContext(
        case_id=8, case_code="CASE-NETBOX-MISSING", title="device missing", summary="",
        source_system="fake_zabbix", source_payload={}, normalized_payload={}, netbox_device_id=None,
        evidence_items=[{
            "id": 8, "evidence_type": "alert", "source_system": "fake_zabbix",
            "summary": "unknown device", "collected_at": datetime.now(timezone.utc),
        }],
    )
    decision = await insight_analysis_agent.run(context)
    assert decision.next_evidence_requests == []
    assert decision.output_payload["hypotheses"][0]["missing_evidence"] == ["NetBox device"]


@pytest.mark.asyncio
async def test_root_cause_unconfirmable_when_no_hypothesis_exists():
    context = AgentExecutionContext(
        case_id=9, case_code="CASE-UNKNOWN", title="unknown", summary="", source_system="fake",
        source_payload={}, normalized_payload={}, evidence_items=[], runtime={"hypotheses": []},
    )
    decision = await diagnostic_critic_agent.run(context)
    assert decision.output_payload["decision"] == "reject"
    assert decision.output_payload["findings"] == [{"code": "no_hypothesis", "evidence_ids": []}]
