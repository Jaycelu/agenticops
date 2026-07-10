"""Converge databases created before Alembic adoption.

Revision ID: 0002_legacy_schema_convergence
Revises: 0001_production_baseline
Create Date: 2026-07-10
"""
from __future__ import annotations

from alembic import op


revision = "0002_legacy_schema_convergence"
down_revision = "0001_production_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Retire the old AlertEvent relationship if an adopted database still has it.
    op.execute(
        """
        DO $$
        DECLARE constraint_name text;
        BEGIN
            FOR constraint_name IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class rel ON rel.oid = c.conrelid
                JOIN pg_class target ON target.oid = c.confrelid
                WHERE rel.relname = 'local_ticket'
                  AND target.relname = 'alert_event'
                  AND c.contype = 'f'
            LOOP
                EXECUTE format('ALTER TABLE local_ticket DROP CONSTRAINT IF EXISTS %I', constraint_name);
            END LOOP;
        END $$
        """
    )
    op.execute("ALTER TABLE local_ticket ADD COLUMN IF NOT EXISTS source_event_id BIGINT")
    op.execute(
        """
        UPDATE local_ticket
        SET source_event_id = NULLIF(metadata->>'source_event_id', '')::BIGINT
        WHERE source_event_id IS NULL
          AND metadata IS NOT NULL
          AND metadata::jsonb ? 'source_event_id'
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_ticket_source_event_provider "
        "ON local_ticket (source_event_id, provider)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_local_ticket_source_event_id "
        "ON local_ticket (source_event_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class rel ON rel.oid = c.conrelid
                JOIN pg_class target ON target.oid = c.confrelid
                WHERE rel.relname = 'local_ticket'
                  AND target.relname = 'source_event'
                  AND c.contype = 'f'
            ) THEN
                ALTER TABLE local_ticket
                ADD CONSTRAINT fk_local_ticket_source_event_id
                FOREIGN KEY (source_event_id) REFERENCES source_event(id);
            END IF;
        END $$
        """
    )

    op.execute("ALTER TABLE source_event ADD COLUMN IF NOT EXISTS legacy_event_id BIGINT")
    op.execute(
        """
        UPDATE source_event
        SET legacy_event_id = NULLIF(normalized_payload->>'legacy_event_id', '')::BIGINT
        WHERE legacy_event_id IS NULL
          AND normalized_payload IS NOT NULL
          AND normalized_payload::jsonb ? 'legacy_event_id'
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_source_event_legacy_event_id "
        "ON source_event (legacy_event_id) WHERE legacy_event_id IS NOT NULL"
    )
    op.execute("ALTER TABLE memory_entry ADD COLUMN IF NOT EXISTS embedding JSON")
    op.execute("ALTER TYPE agenttype ADD VALUE IF NOT EXISTS 'SAFETY_CRITIC'")


def downgrade() -> None:
    # This convergence migration adopts historical production data. Removing columns or
    # enum values would be destructive, so downgrade intentionally preserves the schema.
    pass
