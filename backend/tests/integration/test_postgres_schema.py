from __future__ import annotations

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    from database import engine, get_alembic_config

    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        raise RuntimeError(f"Refusing to reset non-test database: {database_name}")

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    command.upgrade(get_alembic_config(), "head")
    yield


def test_migrations_create_current_schema_on_postgres() -> None:
    from database import engine, init_db

    init_db()

    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1

    tables = set(inspect(engine).get_table_names())
    assert {
        "source_event",
        "case_record",
        "evidence_item",
        "agent_run",
        "agent_claim",
        "remediation_plan",
        "execution_run",
        "identity_provider",
        "user_account",
        "external_identity",
        "role_binding",
        "auth_session",
        "auth_login_transaction",
        "api_token",
        "security_audit_event",
    }.issubset(tables)


def test_upgrade_head_is_idempotent() -> None:
    from database import current_database_revisions, expected_database_revisions, get_alembic_config

    command.upgrade(get_alembic_config(), "head")

    assert current_database_revisions() == expected_database_revisions()


def test_security_audit_table_is_append_only() -> None:
    from audit.service import security_audit_service
    from database import SessionLocal

    db = SessionLocal()
    try:
        first = security_audit_service.append(
            db,
            event_type="auth.integration_test",
            outcome="success",
            details={"sequence": 1},
        )
        db.commit()
        event_id = int(first.id)

        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(
                text("UPDATE security_audit_event SET outcome = 'tampered' WHERE id = :id"),
                {"id": event_id},
            )
        db.rollback()
    finally:
        db.close()
