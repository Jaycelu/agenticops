"""Add server-side one-time login transactions.

Revision ID: 0004_auth_login_transactions
Revises: 0003_auth_foundation
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_auth_login_transactions"
down_revision = "0003_auth_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_login_transaction",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "provider_id",
            sa.Integer(),
            sa.ForeignKey("identity_provider.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("flow_type", sa.String(20), nullable=False),
        sa.Column("encrypted_context", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_login_transaction_provider_id", "auth_login_transaction", ["provider_id"])
    op.create_index("ix_auth_login_transaction_expires_at", "auth_login_transaction", ["expires_at"])
    op.create_index("ix_auth_login_transaction_consumed_at", "auth_login_transaction", ["consumed_at"])
    op.create_index(
        "idx_auth_login_transaction_active",
        "auth_login_transaction",
        ["provider_id", "consumed_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("auth_login_transaction")
