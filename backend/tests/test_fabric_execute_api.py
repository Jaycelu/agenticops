from __future__ import annotations

import itertools

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.fabric import router as fabric_router
from database import Base, get_db
from models import automation  # noqa: F401 - registers FK target tables
from models.agenticops import CaseRecord, CaseStatus, ExecutionRun, RemediationPlan, RemediationPlanStatus
from services import execution_service as execution_service_module
from services.execution_engine import ExecutionResult, ExecutionStatus


def _client_with_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    id_counter = itertools.count(5001)

    def assign_execution_run_id(mapper, connection, target):
        if target.id is None:
            target.id = next(id_counter)

    event.listen(ExecutionRun, "before_insert", assign_execution_run_id)
    app = FastAPI()
    app.include_router(fabric_router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal, assign_execution_run_id


def _seed_plan(SessionLocal):
    db = SessionLocal()
    try:
        case = CaseRecord(
            id=1101,
            case_code="CASE-1101",
            title="API test case",
            status=CaseStatus.PLANNED,
            current_phase="planned",
            device_ip="10.0.0.2",
            host="sw2",
        )
        plan = RemediationPlan(
            id=2101,
            case_id=1101,
            plan_code="PLAN-CASE-1101",
            status=RemediationPlanStatus.DRAFT,
            execution_mode="manual",
            approval_status="not_required",
            risk_level="low",
            summary="api test plan",
            plan_payload={
                "recommended_actions": [
                    {
                        "title": "Notify operator",
                        "action_type": "notification",
                        "tool_id": "notify.dingtalk",
                        "mode": "notify",
                        "message": "Case update",
                    }
                ]
            },
            safety_checks={},
        )
        db.add(case)
        db.add(plan)
        db.commit()
    finally:
        db.close()


def test_execute_plan_endpoint_returns_summary(monkeypatch):
    client, SessionLocal, listener = _client_with_db()
    try:
        _seed_plan(SessionLocal)

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

        response = client.post("/api/fabric/plans/2101/execute", json={"triggered_by": "api-test"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["plan_id"] == 2101
        assert payload["executions"][0]["tool_id"] == "notify.dingtalk"
        assert payload["executions"][0]["allowed"] is True
    finally:
        event.remove(ExecutionRun, "before_insert", listener)


def test_execute_plan_endpoint_returns_404_for_missing_plan():
    client, _, listener = _client_with_db()
    try:
        response = client.post("/api/fabric/plans/9999/execute", json={"triggered_by": "api-test"})

        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"
    finally:
        event.remove(ExecutionRun, "before_insert", listener)
