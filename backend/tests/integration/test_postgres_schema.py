from __future__ import annotations

import pytest
from sqlalchemy import inspect, text


pytestmark = pytest.mark.integration


def test_current_schema_initializes_on_postgres() -> None:
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
    }.issubset(tables)
