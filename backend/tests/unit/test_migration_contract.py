from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_baseline_migration_is_static() -> None:
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0001_production_baseline.py"
    source = path.read_text(encoding="utf-8")

    assert "CREATE TABLE source_event" in source
    assert "CREATE TABLE execution_run" in source
    assert "from models" not in source
    assert "from database" not in source


def test_database_startup_hook_contains_no_schema_mutation() -> None:
    path = Path(__file__).resolve().parents[2] / "database.py"
    source = path.read_text(encoding="utf-8")

    assert "create_all" not in source
    assert "ALTER TABLE" not in source
    assert "verify_database_ready" in source


def test_expected_revision_matches_migration_head() -> None:
    from database import expected_database_revisions

    assert expected_database_revisions() == {"0009_elk_ingestion"}
