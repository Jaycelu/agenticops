"""端到端链路：采样契约、事件 enrich、跨源升格（mock DB）。"""

from unittest.mock import MagicMock, patch

import pytest

from config import pipeline_thresholds
from services.event_decision_service import EventDecisionService, event_decision_service


def test_pipeline_thresholds_match_event_decision_usage():
    assert pipeline_thresholds.CLUSTER_COUNT_NOISE_TO_TICKET >= 1
    assert pipeline_thresholds.CLUSTER_COUNT_TO_CASE >= pipeline_thresholds.CLUSTER_COUNT_NOISE_TO_TICKET
    assert pipeline_thresholds.CROSS_SOURCE_WINDOW_MINUTES >= 5


def test_elk_sampler_maps_to_log_signal():
    svc = EventDecisionService()
    assert svc.get_source_category("ELK_SAMPLER", {}) == "log_signal"
    assert "采样" in svc.get_source_label("ELK_SAMPLER", {})


def test_enrich_cross_source_boosts_ticket_to_case():
    record = MagicMock()
    record.id = 42
    record.source_system = "ELK"
    record.normalized_payload = {"severity_level": 2, "source_category": "log_signal"}
    record.netbox_device_id = 7
    record.host = "h1"
    db = MagicMock()
    decision = {
        "disposition": "ticket_only",
        "reason": "log_signal_requires_followup",
        "confidence": 0.72,
    }
    with patch.object(
        EventDecisionService,
        "_cluster_context_stats",
        return_value={
            "cluster_window_count": 3,
            "open_case_same_anchor": False,
            "cluster_key": "k",
            "cross_source_peer_count": 1,
            "cross_source_window_minutes": 30,
        },
    ):
        out = event_decision_service.enrich_decision_for_context(db, record, decision)
    assert out["disposition"] == "case_required"
    assert out["reason"] == "cross_source_correlation"


def test_log_sampler_policy_signal_summary_shape():
    from services.log_sampler import LogSampler

    sampler = LogSampler()
    stats = {
        "error_count": 0,
        "crc_error_count": 0,
        "flap_count": 0,
        "neighbor_change_count": 0,
        "log_messages": ["%INTERFACE-3-UPDOWN: Line protocol on Interface GigabitEthernet0/1, changed state to down"],
        "critical_messages": [],
        "critical_event_count": 0,
        "hardware_alarm_count": 0,
        "auth_failure_count": 0,
        "routing_instability_count": 0,
        "interface_state_change_count": 0,
        "other_error_count": 0,
    }
    policy = {
        "urgent_levels": ["Critical"],
        "urgent_keywords": [],
        "message_dedup_seconds": 120,
        "immediate_trigger": {},
        "periodic_trigger": {},
    }
    out = sampler._evaluate_collection_policy(
        db=MagicMock(),
        site_id=1,
        site_code="TEST",
        device_ip="10.0.0.1",
        stats=stats,
        collection_policy=policy,
    )
    assert "risk_level" in out or "reason" in out
