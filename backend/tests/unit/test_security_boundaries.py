from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.schemas.automation import ApprovalDecisionRequest, ApprovalInitiateRequest, TaskFeedbackRequest
from api.schemas.events import EventDispatchRequest, EventTicketCreateRequest
from api.schemas.tickets import LocalTicketUpdateRequest
from auth.api_token_service import MACHINE_TOKEN_PERMISSIONS, api_token_digest, api_token_service
from auth.csrf import CSRFMiddleware
from auth.rbac import Permission
from models.auth import ApiToken, UserAccount


pytestmark = pytest.mark.unit


def test_client_identity_fields_are_rejected() -> None:
    invalid_payloads = (
        (ApprovalDecisionRequest, {"decision": "approved", "approver": "forged"}),
        (ApprovalInitiateRequest, {"risk_level": "low", "initiator": "forged"}),
        (TaskFeedbackRequest, {"verdict": "correct", "reviewer": "forged"}),
        (EventDispatchRequest, {"reviewer": "forged"}),
        (EventTicketCreateRequest, {"requester": "forged"}),
        (LocalTicketUpdateRequest, {"status": "closed", "operator": "forged"}),
    )

    for schema, payload in invalid_payloads:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            schema.model_validate(payload)


def test_api_tokens_cannot_receive_human_approval_or_execution_permissions() -> None:
    assert MACHINE_TOKEN_PERMISSIONS == frozenset({Permission.EVENTS_INGEST.value})
    assert Permission.APPROVALS_DECIDE.value not in MACHINE_TOKEN_PERMISSIONS
    assert Permission.EXECUTIONS_RUN.value not in MACHINE_TOKEN_PERMISSIONS


def test_api_token_authentication_is_prefix_scoped_hashed_and_permission_bounded() -> None:
    engine = create_engine("sqlite://")
    UserAccount.__table__.create(engine)
    ApiToken.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    plaintext = "agt_0123456789ab." + "s" * 43
    try:
        db.add(
            UserAccount(
                id=1,
                username="token-owner",
                display_name="Token Owner",
                active=True,
                is_emergency=False,
            )
        )
        db.add(
            ApiToken(
                id=2,
                name="elk-ingest",
                token_prefix="0123456789ab",
                secret_hash=api_token_digest(plaintext),
                permissions=[Permission.EVENTS_INGEST.value, Permission.EXECUTIONS_RUN.value],
                active=True,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                created_by_user_id=1,
            )
        )
        db.commit()

        principal = api_token_service.authenticate(db, plaintext)
        assert principal is not None
        assert principal.auth_type == "api_token"
        assert principal.permissions == frozenset({Permission.EVENTS_INGEST.value})
        assert api_token_service.authenticate(db, plaintext + "wrong") is None
    finally:
        db.close()


def test_csrf_middleware_rejects_cookie_authenticated_mutation_without_double_submit() -> None:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/mutate")
    async def mutate():
        return {"ok": True}

    client = TestClient(app)
    client.cookies.set("agenticops_session", "stale-session")
    response = client.post("/mutate")

    assert response.status_code == 403
    assert response.json() == {"detail": "csrf_validation_failed"}
    client.cookies.clear()
    assert client.post("/mutate").status_code == 200


def test_sensitive_routes_reject_anonymous_requests_before_domain_logic() -> None:
    from main import app

    client = TestClient(app)

    assert client.get("/api/fabric/overview").status_code == 401
    response = client.post(
        "/api/events/ingest",
        json={"source": "ELK", "event_type": "log_signal", "name": "test"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "api_token_required"
