from __future__ import annotations

import pytest
from pydantic import ValidationError

from approvals.service import ApprovalService
from models.agenticops import RemediationPlan
from verifications.baseline import matching_zabbix_alerts
from verifications.schemas import VerificationPolicy


pytestmark = pytest.mark.unit


def valid_policy() -> dict:
    return {
        "checks": [
            {
                "check_id": "originating-alert",
                "kind": "zabbix_alert_absent",
                "target": {"host": "edge-01", "event_id": "101", "name_contains": "uplink down"},
                "max_age_seconds": 300,
            }
        ],
        "max_rounds": 3,
        "interval_seconds": 60,
    }


def test_verification_policy_requires_same_target_identity() -> None:
    assert VerificationPolicy.model_validate(valid_policy()).checks[0].target["event_id"] == "101"
    with pytest.raises(ValidationError, match="event_id or name_contains"):
        VerificationPolicy.model_validate(
            {
                "checks": [
                    {"check_id": "bad", "kind": "zabbix_alert_absent", "target": {"host": "edge-01"}}
                ]
            }
        )


def test_originating_alert_match_does_not_use_total_alert_count() -> None:
    alerts = [
        {"eventid": "100", "name": "CPU high"},
        {"eventid": "101", "name": "Uplink down on Gi0/1"},
        {"eventid": "102", "name": "Another alert"},
    ]

    assert matching_zabbix_alerts(alerts, {"event_id": "101"}) == [alerts[1]]
    assert matching_zabbix_alerts(alerts, {"name_contains": "uplink down"}) == [alerts[1]]
    assert matching_zabbix_alerts(alerts, {"event_id": "999"}) == []


def test_mutation_plan_cannot_be_approved_without_verification_policy() -> None:
    plan = RemediationPlan(
        id=1,
        case_id=2,
        plan_code="PLAN-1",
        plan_payload={
            "recommended_actions": [
                {"tool_id": "ssh.config_change", "credential_id": 3, "commands": ["shutdown"]}
            ]
        },
    )

    with pytest.raises(ValueError, match="requires a valid verification policy"):
        ApprovalService._validate_mutation_verification(plan)
    plan.plan_payload["recommended_actions"][0]["verification"] = valid_policy()
    ApprovalService._validate_mutation_verification(plan)


def test_elk_reduction_policy_bounds_rounds_and_ratio() -> None:
    policy = VerificationPolicy.model_validate(
        {
            "checks": [
                {
                    "check_id": "log-rate",
                    "kind": "elk_count_reduced",
                    "target": {"query": "host:edge-01"},
                    "max_ratio": 0.25,
                }
            ],
            "max_rounds": 5,
            "interval_seconds": 30,
        }
    )

    assert policy.checks[0].max_ratio == 0.25
    with pytest.raises(ValidationError):
        VerificationPolicy.model_validate(
            {"checks": [{"check_id": "bad", "kind": "elk_count_reduced", "target": {"query": "*"}, "max_ratio": 2}]}
        )
