"""Golden-style unit tests for harness contracts (no live PostgreSQL required)."""

import asyncio
from types import SimpleNamespace

from harness.contracts import EvidenceQuerySpec, EpisodeGoal, build_evidence_bundle_dict
from services.event_decision_service import event_decision_service
from services.remediation_recommendation_service import remediation_recommendation_service


def test_evidence_bundle_dict_shape():
    spec = EvidenceQuerySpec(elk_query="host:foo", elk_time_range="-30m,now", elk_limit=100)
    bundle = build_evidence_bundle_dict(
        case_id=42,
        case_code="CASE-42",
        queries=spec,
        evidence_item_ids=[9, 10],
        runtime={"log_summary": {}, "topology": {}},
        notes=["unit"],
    )
    assert bundle["case_id"] == 42
    assert bundle["queries"]["elk_query"] == "host:foo"
    assert 9 in bundle["evidence_item_ids"]
    assert "log_summary" in bundle["runtime_keys"]


def test_episode_goal_roundtrip():
    g = EpisodeGoal(kind="diagnose_only", min_insight_confidence=0.7)
    d = g.to_dict()
    assert EpisodeGoal.from_dict(d).min_insight_confidence == 0.7


def test_evaluate_record_zabbix_high_severity():
    record = SimpleNamespace(
        payload={"severity_level": 4},
        source="ZABBIX",
        severity="high",
        severity_level=4,
        status="open",
        site_id=1,
        netbox_device_id=2,
        host="core-01",
    )
    decision = event_decision_service.evaluate_record(record)
    assert decision["disposition"] == "case_required"


def test_remediation_policy_matches_and_audit():
    acts = remediation_recommendation_service.build_actions(
        root_cause="neighbor flap",
        signal_family="ospf",
        impact_scope="single_device",
        priority="P2",
        cross_source=True,
    )
    audit = remediation_recommendation_service.last_policy_audit
    assert audit.get("matched_rule_id") == "routing_neighbor"
    assert any(a.get("action_type") == "topology_neighbors" for a in acts)
    assert any(a.get("action_type") == "confidence_boost" for a in acts)


def test_alert_triage_emits_next_evidence_requests():
    from agents.alert_triage_agent import alert_triage_agent
    from agents.schemas import AgentExecutionContext

    ctx = AgentExecutionContext(
        case_id=1,
        case_code="C1",
        title="test",
        summary="s",
        source_system="zabbix",
        source_payload={"severity": "high"},
        normalized_payload={"severity": "high"},
        host="h1",
        runtime={},
        evidence_items=[{"id": 1, "evidence_type": "alert", "summary": "x", "payload": {}}],
    )
    decision = asyncio.run(alert_triage_agent.run(ctx))
    assert decision.claim_type == "triage_assessment"
    assert isinstance(decision.next_evidence_requests, list)
