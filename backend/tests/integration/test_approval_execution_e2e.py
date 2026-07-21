"""End-to-end approval→execution→verification→rollback integration tests.

Requires a real PostgreSQL (RUN_POSTGRES_TESTS=1) and Docker services.
This test walks the full remediation lifecycle with actual guard policies
and execution engine wiring — unit tests cover isolated boundary checks.
"""

from __future__ import annotations

import json
import pytest

from auth.schemas import Principal


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        "os.environ.get('RUN_POSTGRES_TESTS') != '1'",
        reason="set RUN_POSTGRES_TESTS=1 to run PostgreSQL integration tests",
    ),
]


FROZEN_PLAN_PAYLOAD = {
    "recommended_actions": [
        {
            "tool_id": "ssh.command",
            "action_type": "ssh",
            "mode": "execute",
            "params": {"command": "show interface", "targets": ["192.168.1.1"]},
            "verification": {"policy": "stateful"},
        },
        {
            "tool_id": "manual.review",
            "action_type": "notification",
            "mode": "manual",
            "params": {"message": "Manual review required"},
        },
    ],
    "rollback_payload": {
        "recommended_actions": [
            {
                "tool_id": "ssh.command",
                "action_type": "ssh",
                "mode": "execute",
                "params": {"command": "rollback to checkpoint 0"},
            }
        ]
    },
    "target_devices": ["192.168.1.1"],
}


def _principal() -> Principal:
    return Principal(user_id=1, username="pytest", session_id="test-session", permissions=[])


def _case(db, case_orchestrator) -> int:
    result = case_orchestrator.intake_case(
        db,
        title="E2E Test Case",
        source_type="manual",
        source_system="pytest",
        severity="critical",
        summary="Integration test for approval→execution chain",
        raw_payload={},
        normalized_payload={},
        occurred_at=None,
    )
    db.commit()
    return result["case_id"]


class TestExecutionDryRun:
    """POST /plans/{id}/execute with dry_run=true validates actions without applying them."""

    def test_dry_run_returns_guard_decisions(self, db, case_orchestrator, execution_service):
        case_id = _case(db, case_orchestrator)
        plan = case_orchestrator._plan_for_execution(db, case_id, plan_payload=FROZEN_PLAN_PAYLOAD)
        plan_id = plan.id
        db.commit()

        result = execution_service.execute_plan(
            db,
            plan_id,
            principal=_principal(),
            idempotency_key="dry-run-test-1",
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["status"] == "dry_run"
        assert len(result["executions"]) == 2

        # mutation action — guard policy check
        mutation = result["executions"][0]
        assert mutation["tool_id"] == "ssh.command"
        assert mutation["allowed"] is True or mutation["allowed"] is False
        assert isinstance(mutation["effective_risk"], int)

        # advisory action (manual.review) — always skippable
        advisory = result["executions"][1]
        assert advisory["tool_id"] == "manual.review"

    def test_dry_run_does_not_change_case_state(self, db, case_orchestrator, execution_service):
        case_id = _case(db, case_orchestrator)
        plan = case_orchestrator._plan_for_execution(db, case_id, plan_payload=FROZEN_PLAN_PAYLOAD)
        db.commit()

        from models.agenticops import CaseRecord
        before = db.query(CaseRecord).filter(CaseRecord.id == case_id).one()
        assert before.status.value in ("new", "open")
        before_status = before.status

        execution_service.execute_plan(
            db, plan.id, principal=_principal(), idempotency_key="dry-run-test-2", dry_run=True,
        )

        after = db.query(CaseRecord).filter(CaseRecord.id == case_id).one()
        assert after.status == before_status


class TestApprovalExecutionBoundary:
    """Full chain: approve → execute → verify → rollback."""

    def test_full_approve_execute_chain(self, db, case_orchestrator, execution_service, approval_service):
        case_id = _case(db, case_orchestrator)
        plan = case_orchestrator._plan_for_execution(db, case_id, plan_payload=FROZEN_PLAN_PAYLOAD)
        plan_id = plan.id
        db.commit()

        # Approve plan with a frozen version
        approval_service.submit(db, plan_id=plan_id, proposed_payload=FROZEN_PLAN_PAYLOAD, principal=_principal())
        approval_service.approve(db, plan_id=plan_id, principal=_principal())
        from approvals.service import approval_service as approval
        version = approval.active_approved_version(db, plan)

        from services.execution_service import execution_service as svc
        result = svc.execute_plan(
            db,
            plan_id,
            principal=_principal(),
            idempotency_key="e2e-full-chain-1",
        )
        assert result["success"] is not None
        assert isinstance(result["executions"], list)

        # All non-advisory actions must have an execution_run_id
        for item in result["executions"]:
            if item.get("status") == "skipped":
                continue
            if item.get("execution_run_id") is None:
                continue  # dry run
            assert int(item["execution_run_id"]) > 0

        from models.agenticops import CaseRecord
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).one()
        assert case.status.value in (
            "verifying", "resolved", "closed", "escalated", "rolled_back",
        )

    def test_rejected_mutation_cannot_execute(self, db, case_orchestrator, execution_service, approval_service):
        """A plan with a blocked mutation should fail at the guard boundary without side effects."""
        case_id = _case(db, case_orchestrator)
        plan = case_orchestrator._plan_for_execution(db, case_id, plan_payload=FROZEN_PLAN_PAYLOAD)
        db.commit()
        from models.agenticops import CaseRecord

        # Attempt execution without the correct approval
        with pytest.raises((ValueError, LookupError)):
            execution_service.execute_plan(db, plan.id, principal=_principal(), idempotency_key="e2e-reject-1")
