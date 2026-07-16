from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from sqlalchemy import text


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def migrated_graph_database():
    from database import engine, get_alembic_config

    if not (engine.url.database or "").endswith("_test"):
        raise RuntimeError("refusing to reset non-test database")
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(get_alembic_config(), "head")
    yield


def _create_case(*, direct_evidence: bool = True, netbox_device_id: int | None = 101) -> tuple[int, int | None]:
    from database import SessionLocal
    from models.agenticops import CaseRecord, EvidenceItem, EvidenceType, SourceEvent, SourceEventStatus

    db = SessionLocal()
    try:
        suffix = datetime.now(timezone.utc).timestamp()
        source = SourceEvent(
            source_type="fake", source_system="fake-zabbix", dedup_key=f"fake:{suffix}",
            title="BGP neighbor down", severity="high", status=SourceEventStatus.CASE_CREATED,
            raw_payload={"severity": "high"}, normalized_payload={"neighbor": "192.0.2.1"},
            netbox_device_id=netbox_device_id,
        )
        db.add(source)
        db.flush()
        case = CaseRecord(
            case_code=f"CASE-TEST-{source.id}", title=source.title, source_event_id=source.id,
            netbox_device_id=netbox_device_id, priority="P1", risk_level="high",
        )
        db.add(case)
        db.flush()
        evidence_id = None
        if direct_evidence:
            evidence = EvidenceItem(
                case_id=case.id, source_event_id=source.id, evidence_type=EvidenceType.COMMAND_OUTPUT,
                source_system="fake_probe", source_ref=f"fake:{source.id}", summary="BGP peer is Idle",
                payload={"peer": "192.0.2.1", "state": "Idle"}, confidence=1.0,
                occurred_at=datetime.now(timezone.utc), collected_at=datetime.now(timezone.utc),
            )
            db.add(evidence)
            db.flush()
            evidence_id = int(evidence.id)
        else:
            db.add(EvidenceItem(
                case_id=case.id, source_event_id=source.id, evidence_type=EvidenceType.ALERT,
                source_system="fake-zabbix", source_ref=f"alert:{source.id}", summary=source.title,
                payload={"severity": "high"}, confidence=1.0,
                occurred_at=datetime.now(timezone.utc), collected_at=datetime.now(timezone.utc),
            ))
        db.commit()
        return int(case.id), evidence_id
    finally:
        db.close()
async def _fake_runtime(*args, **kwargs):
    return {"device": {"name": "edge-1", "role": "edge", "site": "lab"}, "fake_adapter": True}


async def _fake_hypothesis(payload):
    evidence = payload.get("evidence_items_index") or []
    direct_ids = [int(item["id"]) for item in evidence if item.get("evidence_type") == "command_output"]
    supporting = direct_ids[:1] or [int(evidence[0]["id"])]
    return {
        "root_cause": "bgp_peer_transport_failure",
        "confidence": 0.91,
        "summary": "Direct device evidence shows the BGP peer is Idle.",
        "cited_evidence_ids": supporting,
        "hypotheses": [{
            "id": "h1", "cause_code": "bgp_peer_transport_failure", "cause": "BGP transport is unavailable",
            "confidence": 0.91, "supporting_evidence_ids": supporting, "contradicting_evidence_ids": [],
            "missing_evidence": [], "next_probe_requests": [], "status": "supported",
        }],
    }


async def _fake_hypothesis_with_evidence_gap(payload):
    evidence = payload.get("evidence_items_index") or []
    direct_ids = [int(item["id"]) for item in evidence if item.get("evidence_type") == "command_output"]
    support = direct_ids[:1] or [int(evidence[0]["id"])]
    request = [] if direct_ids else [{
        "probe_id": "network.bgp.neighbor_detail",
        "target": {"netbox_device_id": int(payload["case"]["netbox_device_id"])},
        "parameters": {"neighbor": "192.0.2.1"},
        "reason": "verify BGP session state",
        "expected_evidence_type": "command_output",
    }]
    return {
        "root_cause": "bgp_peer_transport_failure" if direct_ids else "unknown",
        "confidence": 0.92 if direct_ids else 0.48,
        "summary": "BGP evidence evaluated",
        "cited_evidence_ids": support,
        "hypotheses": [{
            "id": "h1", "cause_code": "bgp_peer_transport_failure", "cause": "BGP transport is unavailable",
            "confidence": 0.92 if direct_ids else 0.48,
            "supporting_evidence_ids": support, "contradicting_evidence_ids": [],
            "missing_evidence": [] if direct_ids else ["BGP neighbor state"],
            "next_probe_requests": request, "status": "supported" if direct_ids else "proposed",
        }],
    }


@pytest.mark.asyncio
async def test_async_graph_reaches_planning_and_observe_only_stop(monkeypatch):
    from agents.insight_analysis_agent import insight_analysis_agent
    from database import SessionLocal
    from engines.case_orchestrator import case_orchestrator
    from models.agent_graph import AgentGraphRun, AgentTask, CaseHypothesis, CaseTimelineEvent
    from models.agenticops import CaseRecord, ExecutionRun, RemediationPlan
    from orchestration.graph_service import graph_service
    from orchestration.graph_worker import agent_graph_worker

    monkeypatch.setattr(case_orchestrator, "_collect_runtime_context", _fake_runtime)
    monkeypatch.setattr(insight_analysis_agent, "_infer_with_llm", _fake_hypothesis)
    case_id, evidence_id = _create_case(direct_evidence=True)
    db = SessionLocal()
    try:
        run, duplicate = graph_service.enqueue(db, case_id=case_id, input_payload={})
        graph_run_id = run.id
        assert duplicate is False
        same, duplicate = graph_service.enqueue(db, case_id=case_id, input_payload={})
        assert duplicate is True and same.id == graph_run_id
    finally:
        db.close()

    for _ in range(40):
        progressed = await agent_graph_worker.run_once()
        db = SessionLocal()
        try:
            status = db.query(AgentGraphRun.status).filter(AgentGraphRun.id == graph_run_id).scalar()
        finally:
            db.close()
        if status in {"completed", "failed", "budget_exhausted"}:
            break
        assert progressed

    db = SessionLocal()
    try:
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == graph_run_id).one()
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).one()
        assert run.status == "completed"
        assert run.stop_reason == "observe_only_stop"
        assert case.status.value == "observing"
        assert db.query(RemediationPlan).filter(RemediationPlan.case_id == case_id).count() == 1
        assert db.query(ExecutionRun).filter(ExecutionRun.case_id == case_id).count() == 0
        assert db.query(CaseHypothesis).filter(
            CaseHypothesis.graph_run_id == graph_run_id, CaseHypothesis.status == "confirmed"
        ).count() == 1
        nodes = {item[0] for item in db.query(AgentTask.graph_node).filter(AgentTask.graph_run_id == graph_run_id).all()}
        assert {"normalize", "triage", "supervisor", "evidence_collection", "historical", "diagnostic", "critic", "plan_candidate", "safety_review"}.issubset(nodes)
        assert db.query(CaseTimelineEvent).filter(CaseTimelineEvent.graph_run_id == graph_run_id).count() >= 10
    finally:
        db.close()


@pytest.mark.asyncio
async def test_expired_worker_lease_resumes_running_task(monkeypatch):
    from database import SessionLocal
    from engines.case_orchestrator import case_orchestrator
    from models.agent_graph import AgentGraphRun, AgentTask, AgentCheckpoint
    from orchestration.graph_service import graph_service
    from orchestration.graph_worker import agent_graph_worker

    monkeypatch.setattr(case_orchestrator, "_collect_runtime_context", _fake_runtime)
    case_id, _ = _create_case(direct_evidence=True)
    db = SessionLocal()
    try:
        run, _ = graph_service.enqueue(db, case_id=case_id, input_payload={})
        task = db.query(AgentTask).filter(AgentTask.graph_run_id == run.id).one()
        run.status = "running"
        run.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        run.lease_owner = "dead-worker"
        run.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        task.status = "running"
        db.commit()
        run_id = run.id
    finally:
        db.close()

    assert await agent_graph_worker.run_once() is True
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.graph_run_id == run_id, AgentTask.graph_node == "normalize").one()
        assert task.status == "completed"
        assert db.query(AgentCheckpoint).filter(AgentCheckpoint.graph_run_id == run_id).count() == 1
        # Keep this module's shared worker queue isolated for the following test.
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
        run.status = "cancelled"
        run.stop_reason = "test_cleanup"
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_budget_exhaustion_stops_graph_before_agent_run():
    from database import SessionLocal
    from models.agent_graph import AgentBudget, AgentGraphRun
    from models.agenticops import CaseRecord
    from orchestration.graph_service import graph_service
    from orchestration.graph_worker import agent_graph_worker

    case_id, _ = _create_case(direct_evidence=True)
    db = SessionLocal()
    try:
        run, _ = graph_service.enqueue(db, case_id=case_id, input_payload={})
        budget = db.query(AgentBudget).filter(AgentBudget.graph_run_id == run.id).one()
        budget.max_agent_runs = 0
        db.commit()
        run_id = run.id
    finally:
        db.close()
    assert await agent_graph_worker.run_once() is True  # normalize
    assert await agent_graph_worker.run_once() is True  # triage -> budget exhausted
    db = SessionLocal()
    try:
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).one()
        budget = db.query(AgentBudget).filter(AgentBudget.graph_run_id == run_id).one()
        assert run.status == "budget_exhausted"
        assert case.status.value == "escalated"
        assert budget.exhausted is True
        assert budget.exhausted_reason == "agent_runs"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_evidence_request_closes_loop_and_triggers_second_diagnostic_round(monkeypatch):
    from agents.insight_analysis_agent import insight_analysis_agent
    from database import SessionLocal
    from engines.case_orchestrator import case_orchestrator
    from models.agent_graph import AgentGraphRun, AgentMessage, AgentTask, AgentToolCall
    from models.agenticops import EvidenceItem
    from models.automation import SSHCredential
    from models.probe import ProbeRun
    from orchestration.graph_service import graph_service
    from orchestration.graph_worker import agent_graph_worker
    from probes.gateway import probe_gateway
    from probes.schemas import EvidenceEnvelope, ProbeResult

    monkeypatch.setattr(case_orchestrator, "_collect_runtime_context", _fake_runtime)
    monkeypatch.setattr(insight_analysis_agent, "_infer_with_llm", _fake_hypothesis_with_evidence_gap)

    def fake_probe_run(db, request, principal=None):
        probe_run = ProbeRun(
            probe_id=request.probe_id,
            template_version="fake-v1",
            netbox_device_id=request.netbox_device_id,
            credential_id=request.credential_id,
            status="succeeded",
            request_parameters=request.parameters,
            rendered_commands=["registered-template"],
            evidence={"adapter": "fake"},
            finished_at=datetime.now(timezone.utc),
        )
        db.add(probe_run)
        db.flush()
        return ProbeResult(
            run_id=probe_run.id,
            status="succeeded",
            evidence=EvidenceEnvelope(
                probe_id=request.probe_id,
                template_version="fake-v1",
                netbox_device_id=request.netbox_device_id,
                collected_at=datetime.now(timezone.utc),
                outputs=[{"command": "registered-template", "output": "BGP state Idle", "stderr": ""}],
            ),
        )

    monkeypatch.setattr(probe_gateway, "run", fake_probe_run)
    case_id, _ = _create_case(direct_evidence=False)
    db = SessionLocal()
    try:
        credential = SSHCredential(name=f"fake-{case_id}", username="fake", auth_type="password", enabled=True)
        db.add(credential)
        db.flush()
        run, _ = graph_service.enqueue(db, case_id=case_id, input_payload={"credential_id": credential.id})
        run_id = run.id
    finally:
        db.close()

    for _ in range(50):
        assert await agent_graph_worker.run_once() is True
        db = SessionLocal()
        try:
            state = db.query(AgentGraphRun.status).filter(AgentGraphRun.id == run_id).scalar()
        finally:
            db.close()
        if state in {"completed", "failed", "budget_exhausted"}:
            break

    db = SessionLocal()
    try:
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
        diagnostic_rounds = [item[0] for item in db.query(AgentTask.insight_round).filter(
            AgentTask.graph_run_id == run_id,
            AgentTask.graph_node == "diagnostic",
            AgentTask.status == "completed",
        ).order_by(AgentTask.insight_round.asc()).all()]
        call = db.query(AgentToolCall).filter(AgentToolCall.graph_run_id == run_id).one()
        evidence = db.query(EvidenceItem).filter(EvidenceItem.tool_call_id == call.id).one()
        response = db.query(AgentMessage).filter(
            AgentMessage.graph_run_id == run_id,
            AgentMessage.message_type == "evidence_response",
        ).one()
        assert run.status == "completed"
        assert diagnostic_rounds == [0, 1]
        assert call.tool_id == "network.bgp.neighbor_detail"
        assert call.mode == "observe" and call.status == "completed"
        assert evidence.source_system == "probe_gateway"
        assert response.content["evidence_id"] == evidence.id
    finally:
        db.close()


def test_force_restart_preserves_artifacts_and_audits_old_run():
    from auth.schemas import Principal
    from database import SessionLocal
    from models.agent_graph import AgentGraphRun, AgentTask, CaseTimelineEvent
    from models.agenticops import EvidenceItem
    from models.auth import SecurityAuditEvent, UserAccount
    from orchestration.graph_service import graph_service

    case_id, evidence_id = _create_case(direct_evidence=True)
    db = SessionLocal()
    try:
        user = UserAccount(username=f"graph-admin-{case_id}", display_name="Graph Admin")
        db.add(user)
        db.flush()
        principal = Principal(
            user_id=user.id, username=user.username, display_name=user.display_name, roles=frozenset({"admin"}),
            permissions=frozenset({"agent_graphs.restart"}), session_id=None,
        )
        old, _ = graph_service.enqueue(db, case_id=case_id, input_payload={})
        new, duplicate = graph_service.enqueue(
            db, case_id=case_id, input_payload={}, principal=principal, force_restart=True,
        )
        db.expire_all()
        old = db.query(AgentGraphRun).filter(AgentGraphRun.id == old.id).one()
        assert duplicate is False
        assert old.status == "cancelled"
        assert new.id != old.id and new.forced_from_run_id == old.id
        assert db.query(AgentTask).filter(AgentTask.graph_run_id == old.id, AgentTask.status == "cancelled").count() == 1
        assert db.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).count() == 1
        assert db.query(CaseTimelineEvent).filter(
            CaseTimelineEvent.graph_run_id == old.id,
            CaseTimelineEvent.title == "Graph run cancelled by force restart",
        ).count() == 1
        assert db.query(SecurityAuditEvent).filter(
            SecurityAuditEvent.event_type == "agent_graph.force_restart",
            SecurityAuditEvent.target_id == new.id,
        ).count() == 1
        new.status = "cancelled"
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_missing_probe_credential_waits_for_human_without_tool_execution(monkeypatch):
    from agents.insight_analysis_agent import insight_analysis_agent
    from database import SessionLocal
    from engines.case_orchestrator import case_orchestrator
    from models.agent_graph import AgentGraphRun, AgentMessage, AgentTask, AgentToolCall
    from orchestration.graph_service import graph_service
    from orchestration.graph_worker import agent_graph_worker

    monkeypatch.setattr(case_orchestrator, "_collect_runtime_context", _fake_runtime)
    monkeypatch.setattr(insight_analysis_agent, "_infer_with_llm", _fake_hypothesis_with_evidence_gap)
    case_id, _ = _create_case(direct_evidence=False)
    db = SessionLocal()
    try:
        run, _ = graph_service.enqueue(db, case_id=case_id, input_payload={})
        run_id = run.id
    finally:
        db.close()
    for _ in range(30):
        assert await agent_graph_worker.run_once() is True
        db = SessionLocal()
        try:
            state = db.query(AgentGraphRun.status).filter(AgentGraphRun.id == run_id).scalar()
        finally:
            db.close()
        if state == "waiting_human":
            break
    db = SessionLocal()
    try:
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
        waiting = db.query(AgentTask).filter(
            AgentTask.graph_run_id == run_id, AgentTask.status == "waiting_human",
        ).one()
        assert run.status == "waiting_human" and run.current_node == "human_gate"
        assert waiting.error_message == "credential_required_for_probe"
        assert db.query(AgentToolCall).filter(AgentToolCall.graph_run_id == run_id).count() == 0
        assert db.query(AgentMessage).filter(
            AgentMessage.graph_run_id == run_id, AgentMessage.message_type == "human_handoff",
        ).count() == 1
        run.status = "cancelled"
        waiting.status = "cancelled"
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_repeated_node_failure_is_bounded(monkeypatch):
    from database import SessionLocal
    from engines.case_orchestrator import case_orchestrator
    from models.agent_graph import AgentGraphRun, AgentTask
    from orchestration.graph_service import graph_service
    from orchestration.graph_worker import agent_graph_worker

    async def broken_runtime(*args, **kwargs):
        raise RuntimeError("fake adapter unavailable")

    monkeypatch.setattr(case_orchestrator, "_collect_runtime_context", broken_runtime)
    case_id, _ = _create_case(direct_evidence=True)
    db = SessionLocal()
    try:
        run, _ = graph_service.enqueue(db, case_id=case_id, input_payload={})
        run_id = run.id
    finally:
        db.close()

    for _ in range(20):
        assert await agent_graph_worker.run_once() is True
        db = SessionLocal()
        try:
            state = db.query(AgentGraphRun.status).filter(AgentGraphRun.id == run_id).scalar()
        finally:
            db.close()
        if state == "failed":
            break
    db = SessionLocal()
    try:
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
        task = db.query(AgentTask).filter(
            AgentTask.graph_run_id == run_id, AgentTask.graph_node == "evidence_collection",
        ).one()
        assert run.status == "failed"
        assert task.status == "failed"
        assert task.attempt_count == task.max_attempts == 3
        assert "RuntimeError" in task.error_message
    finally:
        db.close()


@pytest.mark.asyncio
async def test_async_case_api_acceptance_and_graph_query_contracts():
    from fastapi import HTTPException

    from api.cases import (
        get_case_agent_budget,
        get_case_graph_run,
        get_case_hypotheses,
        get_case_timeline,
        list_case_graph_runs,
        run_case_agents,
    )
    from auth.rbac import Permission
    from auth.schemas import Principal
    from database import SessionLocal
    from models.agent_graph import AgentGraphRun
    from models.auth import UserAccount

    case_id, _ = _create_case(direct_evidence=True)
    db = SessionLocal()
    try:
        user = UserAccount(username=f"api-operator-{case_id}", display_name="API Operator")
        db.add(user)
        db.commit()
        principal = Principal(
            user_id=user.id, username=user.username, display_name=user.display_name,
            roles=frozenset({"operator"}), permissions=frozenset({Permission.PROBES_RUN.value}), session_id=None,
        )
        accepted = await run_case_agents(
            case_id=case_id, base_name=None, log_query=None, time_range="-15m,now", log_limit=200,
            credential_id=None, force_restart=False, wait=False, timeout_seconds=30,
            principal=principal, db=db,
        )
        assert accepted.status == "accepted"
        assert accepted.execution_mode == "async"
        assert accepted.queued is True and accepted.already_running is False
        run_id = accepted.graph_run_id

        duplicate = await run_case_agents(
            case_id=case_id, base_name=None, log_query=None, time_range="-15m,now", log_limit=200,
            credential_id=None, force_restart=False, wait=False, timeout_seconds=30,
            principal=principal, db=db,
        )
        assert duplicate.status == "running" and duplicate.graph_run_id == run_id
        assert duplicate.already_running is True

        runs = await list_case_graph_runs(case_id, db)
        detail = await get_case_graph_run(case_id, run_id, db)
        timeline = await get_case_timeline(case_id, 500, db)
        hypotheses = await get_case_hypotheses(case_id, db)
        budget = await get_case_agent_budget(case_id, run_id, db)
        assert len(runs["items"]) == 1
        assert detail["graph_run_id"] == run_id and detail["tasks"][0]["graph_node"] == "normalize"
        assert timeline["items"][0]["event_type"] == "agent_task"
        assert hypotheses["items"] == []
        assert budget["limits"]["probe_calls"] == 10 and budget["usage"]["probe_calls"] == 0

        with pytest.raises(HTTPException) as exc:
            await run_case_agents(
                case_id=case_id, base_name=None, log_query=None, time_range="-15m,now", log_limit=200,
                credential_id=None, force_restart=True, wait=False, timeout_seconds=30,
                principal=principal, db=db,
            )
        assert exc.value.status_code == 403
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
        run.status = "cancelled"
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_expired_task_deadline_times_out_graph_and_escalates_case():
    from database import SessionLocal
    from models.agent_graph import AgentCheckpoint, AgentGraphRun, AgentTask
    from models.agenticops import CaseRecord
    from orchestration.graph_service import graph_service
    from orchestration.graph_worker import agent_graph_worker

    case_id, _ = _create_case(direct_evidence=True)
    db = SessionLocal()
    try:
        run, _ = graph_service.enqueue(db, case_id=case_id, input_payload={})
        task = db.query(AgentTask).filter(AgentTask.graph_run_id == run.id).one()
        task.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        run_id = run.id
    finally:
        db.close()
    assert await agent_graph_worker.run_once() is True
    db = SessionLocal()
    try:
        run = db.query(AgentGraphRun).filter(AgentGraphRun.id == run_id).one()
        task = db.query(AgentTask).filter(AgentTask.graph_run_id == run_id).one()
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).one()
        assert run.status == "timed_out"
        assert task.status == "timed_out"
        assert case.status.value == "escalated"
        assert db.query(AgentCheckpoint).filter(AgentCheckpoint.graph_run_id == run_id).count() == 1
    finally:
        db.close()
