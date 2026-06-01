from __future__ import annotations

import asyncio
import itertools
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from database import Base
from models import automation  # noqa: F401 - registers FK target tables
from models.agenticops import (
    CaseRecord,
    CaseStatus,
    ExecutionRun,
    ExecutionRunStatus,
    RemediationPlan,
    RemediationPlanStatus,
)
from services import execution_service as execution_service_module
from services.execution_engine import ExecutionResult, ExecutionStatus
from services.execution_service import ExecutionService


import pytest


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    id_counter = itertools.count(3001)

    def assign_execution_run_id(mapper, connection, target):
        if target.id is None:
            target.id = next(id_counter)

    event.listen(ExecutionRun, "before_insert", assign_execution_run_id)
    try:
        yield db
    finally:
        event.remove(ExecutionRun, "before_insert", assign_execution_run_id)
        db.close()


def _case_and_plan(db, *, actions, approval_status="required"):
    case = CaseRecord(
        id=1001,
        case_code="CASE-1001",
        title="Test case",
        status=CaseStatus.PLANNED,
        current_phase="planned",
        device_ip="10.0.0.1",
        host="sw1",
        risk_level="medium",
    )
    plan = RemediationPlan(
        id=2001,
        case_id=1001,
        plan_code="PLAN-CASE-1001",
        status=RemediationPlanStatus.DRAFT,
        execution_mode="manual",
        approval_status=approval_status,
        risk_level="medium",
        summary="test plan",
        plan_payload={"recommended_actions": actions},
        safety_checks={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(case)
    db.add(plan)
    db.commit()
    return case, plan


def test_execute_plan_records_blocked_execution_run(db_session):
    _, plan = _case_and_plan(
        db_session,
        actions=[
            {
                "title": "Unsafe command",
                "action_type": "ssh_config_change",
                "tool_id": "ssh.config_change",
                "mode": "execute",
                "commands": ["reboot"],
            }
        ],
    )

    result = asyncio.run(ExecutionService().execute_plan(db_session, int(plan.id), triggered_by="pytest"))

    run = db_session.query(ExecutionRun).one()
    assert not result["success"]
    assert run.status == ExecutionRunStatus.FAILED
    assert run.error_message == "approval_required"
    assert run.audit_trail[0]["action"] == "policy_guard"
    assert run.audit_trail[0]["decision"]["blocked_reason"] == "approval_required"


def test_execute_plan_records_allowed_execution_run(db_session, monkeypatch):
    _, plan = _case_and_plan(
        db_session,
        actions=[
            {
                "title": "Notify operator",
                "action_type": "notification",
                "tool_id": "notify.dingtalk",
                "mode": "notify",
                "message": "Case update",
            }
        ],
        approval_status="not_required",
    )

    async def fake_execute_action(task_id, action_type, action_config, context, retry_policy=None):
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message="ok",
            details={"task_id": task_id, "executor": action_type.value},
            output={"sent": True},
        )

    async def fake_verify(db, *, execution_id):
        return {"success": True, "execution_id": execution_id, "verdict": "verified"}

    monkeypatch.setattr(execution_service_module.execution_engine, "execute_action", fake_execute_action)
    monkeypatch.setattr(
        execution_service_module.post_execution_verification_service,
        "verify_execution_readonly",
        fake_verify,
    )

    result = asyncio.run(ExecutionService().execute_plan(db_session, int(plan.id), triggered_by="pytest"))

    run = db_session.query(ExecutionRun).one()
    db_session.refresh(plan)
    assert result["success"]
    assert run.status == ExecutionRunStatus.SUCCEEDED
    assert run.result_payload["status"] == "success"
    assert run.result_payload["post_verification"]["verdict"] == "verified"
    assert plan.status == RemediationPlanStatus.SUCCEEDED


def test_execute_plan_blocks_approved_mutation_in_observe_only(db_session):
    _, plan = _case_and_plan(
        db_session,
        actions=[
            {
                "title": "Run approved script",
                "action_type": "script_run",
                "tool_id": "script.run",
                "mode": "execute",
                "script_path": "fix_interface.sh",
            }
        ],
        approval_status="approved",
    )

    result = asyncio.run(ExecutionService().execute_plan(db_session, int(plan.id), triggered_by="pytest"))

    run = db_session.query(ExecutionRun).one()
    assert not result["success"]
    assert run.status == ExecutionRunStatus.FAILED
    assert run.error_message == "observe_only_blocked"
    assert run.audit_trail[0]["decision"]["blocked_reason"] == "observe_only_blocked"


def test_execute_plan_handles_partial_failure(db_session, monkeypatch):
    _, plan = _case_and_plan(
        db_session,
        actions=[
            {
                "title": "Notify operator",
                "action_type": "notification",
                "tool_id": "notify.dingtalk",
                "mode": "notify",
                "message": "Case update",
            },
            {
                "title": "Unsafe command",
                "action_type": "ssh_config_change",
                "tool_id": "ssh.config_change",
                "mode": "execute",
                "commands": ["reboot"],
            },
        ],
        approval_status="not_required",
    )

    async def fake_execute_action(task_id, action_type, action_config, context, retry_policy=None):
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message="ok")

    async def fake_verify(db, *, execution_id):
        return {"success": True, "execution_id": execution_id, "verdict": "inconclusive"}

    monkeypatch.setattr(execution_service_module.execution_engine, "execute_action", fake_execute_action)
    monkeypatch.setattr(
        execution_service_module.post_execution_verification_service,
        "verify_execution_readonly",
        fake_verify,
    )

    result = asyncio.run(ExecutionService().execute_plan(db_session, int(plan.id), triggered_by="pytest"))

    runs = db_session.query(ExecutionRun).order_by(ExecutionRun.id.asc()).all()
    db_session.refresh(plan)
    assert not result["success"]
    assert [run.status for run in runs] == [ExecutionRunStatus.SUCCEEDED, ExecutionRunStatus.FAILED]
    assert plan.status == RemediationPlanStatus.FAILED


def test_execute_plan_circuit_breaker_blocks_repeated_target(db_session):
    _, plan = _case_and_plan(
        db_session,
        actions=[
            {
                "title": "Notify operator",
                "action_type": "notification",
                "tool_id": "notify.dingtalk",
                "mode": "notify",
                "message": "Case update",
            }
        ],
        approval_status="not_required",
    )
    for idx in range(3):
        db_session.add(
            ExecutionRun(
                case_id=1001,
                remediation_plan_id=2001,
                executor_type="notification",
                executor_name="prior",
                status=ExecutionRunStatus.SUCCEEDED,
                command_summary=f"prior-{idx}",
                request_payload={"target_id": "10.0.0.1"},
                result_payload={},
                audit_trail=[],
                started_at=datetime.now(timezone.utc),
            )
        )
    db_session.commit()

    result = asyncio.run(ExecutionService().execute_plan(db_session, int(plan.id), triggered_by="pytest"))

    latest = db_session.query(ExecutionRun).order_by(ExecutionRun.id.desc()).first()
    assert not result["success"]
    assert latest.status == ExecutionRunStatus.FAILED
    assert latest.error_message == "circuit_breaker"


# ---------------------------------------------------------------------------
# Phase 1.5 — advisory (manual.review) actions are skipped, not failed
# ---------------------------------------------------------------------------


def test_execute_plan_skips_advisory_manual_review_action(db_session):
    _, plan = _case_and_plan(
        db_session,
        actions=[
            {
                "title": "Cross-source review",
                "action_type": "cross_source_review",
                "tool_id": "manual.review",
                "mode": "manual_check",
            }
        ],
        approval_status="not_required",
    )

    result = asyncio.run(ExecutionService().execute_plan(db_session, int(plan.id), triggered_by="pytest"))

    db_session.refresh(plan)
    # advisory action -> no ExecutionRun, recorded as skipped, not a failure
    assert db_session.query(ExecutionRun).count() == 0
    assert result["success"] is True
    assert result["executions"][0]["status"] == "skipped"
    assert result["executions"][0]["execution_run_id"] is None
    # all-advisory plan reverts to DRAFT
    assert plan.status == RemediationPlanStatus.DRAFT


def test_execute_plan_advisory_alongside_executable_action(db_session, monkeypatch):
    _, plan = _case_and_plan(
        db_session,
        actions=[
            {
                "title": "Notify operator",
                "action_type": "notification",
                "tool_id": "notify.dingtalk",
                "mode": "notify",
                "message": "Case update",
            },
            {
                "title": "Cross-source review",
                "action_type": "cross_source_review",
                "tool_id": "manual.review",
                "mode": "manual_check",
            },
        ],
        approval_status="not_required",
    )

    async def fake_execute_action(task_id, action_type, action_config, context, retry_policy=None):
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message="ok", output={"sent": True})

    async def fake_verify(db, *, execution_id):
        return {"success": True, "execution_id": execution_id, "verdict": "verified"}

    monkeypatch.setattr(execution_service_module.execution_engine, "execute_action", fake_execute_action)
    monkeypatch.setattr(
        execution_service_module.post_execution_verification_service,
        "verify_execution_readonly",
        fake_verify,
    )

    result = asyncio.run(ExecutionService().execute_plan(db_session, int(plan.id), triggered_by="pytest"))

    statuses = [item["status"] for item in result["executions"]]
    assert "skipped" in statuses
    # only the notification produced an ExecutionRun; the advisory action was skipped
    assert db_session.query(ExecutionRun).count() == 1
    assert result["success"] is True
