"""Validate an existing AgenticOps schema, stamp the baseline, and converge it."""
from __future__ import annotations

import argparse

from alembic import command
from sqlalchemy import inspect

from database import engine, get_alembic_config
from database_schema import active_table_names


BASELINE_REVISION = "0001_production_baseline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Adopt Alembic for an existing database without replaying CREATE TABLE statements."
    )
    parser.add_argument(
        "--confirm-existing-schema",
        action="store_true",
        help="required acknowledgement that the target is an existing AgenticOps database",
    )
    return parser.parse_args()


def validate_existing_schema() -> None:
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    if "alembic_version" in existing:
        raise RuntimeError("Database is already managed by Alembic; run 'alembic upgrade head' instead.")

    required = active_table_names()
    missing = sorted(required - existing)
    if missing:
        raise RuntimeError(
            "Existing schema does not match the adoption baseline; missing tables: " + ", ".join(missing)
        )

    required_columns = {
        "source_event": {"id", "normalized_payload"},
        "local_ticket": {"id", "metadata"},
        "memory_entry": {"id"},
        "agent_run": {"id", "agent_type"},
    }
    for table_name, expected_columns in required_columns.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = sorted(expected_columns - actual_columns)
        if missing_columns:
            raise RuntimeError(
                f"Existing table {table_name} is missing baseline columns: {', '.join(missing_columns)}"
            )


def main() -> None:
    args = parse_args()
    if not args.confirm_existing_schema:
        raise SystemExit("Refusing to stamp without --confirm-existing-schema")

    validate_existing_schema()
    config = get_alembic_config()
    command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")
    print("Existing schema adopted and upgraded to Alembic head.")


if __name__ == "__main__":
    main()
