"""Add the automatic read-only probe gateway schema.

Revision ID: 0005_probe_gateway
Revises: 0004_auth_login_transactions
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_probe_gateway"
down_revision = "0004_auth_login_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ssh_credential",
        sa.Column(
            "capability_scope",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[\"probe.read\"]'::json"),
        ),
    )
    op.create_table(
        "device_host_key",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("netbox_device_id", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("algorithm", sa.String(80), nullable=False),
        sa.Column("public_key_base64", sa.Text(), nullable=False),
        sa.Column("fingerprint_sha256", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verified_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_device_host_key_netbox_device_id", "device_host_key", ["netbox_device_id"])
    op.create_index("ix_device_host_key_active", "device_host_key", ["active"])
    op.create_index(
        "uq_device_host_key_active",
        "device_host_key",
        ["netbox_device_id", "port"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE"),
    )
    op.create_table(
        "probe_template_version",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("probe_id", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("catalog_hash", sa.String(64), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_probe_template_version_probe_id", "probe_template_version", ["probe_id"])
    op.create_index("ix_probe_template_version_active", "probe_template_version", ["active"])
    op.create_index("uq_probe_template_version", "probe_template_version", ["probe_id", "version"], unique=True)
    op.create_table(
        "probe_run",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("probe_id", sa.String(120), nullable=False),
        sa.Column("template_version", sa.String(40), nullable=False),
        sa.Column("netbox_device_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.Integer(), sa.ForeignKey("ssh_credential.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="SET NULL")),
        sa.Column("requested_by_session_id", sa.String(64)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("request_parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("rendered_commands", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_detail", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_probe_run_probe_id", "probe_run", ["probe_id"])
    op.create_index("ix_probe_run_netbox_device_id", "probe_run", ["netbox_device_id"])
    op.create_index("ix_probe_run_credential_id", "probe_run", ["credential_id"])
    op.create_index("ix_probe_run_requested_by_user_id", "probe_run", ["requested_by_user_id"])
    op.create_index("ix_probe_run_requested_by_session_id", "probe_run", ["requested_by_session_id"])
    op.create_index("ix_probe_run_status", "probe_run", ["status"])
    op.create_index("idx_probe_run_device_started", "probe_run", ["netbox_device_id", "started_at"])
    op.create_index(
        "uq_probe_run_device_running",
        "probe_run",
        ["netbox_device_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_table("probe_run")
    op.drop_table("probe_template_version")
    op.drop_table("device_host_key")
    op.drop_column("ssh_credential", "capability_scope")
