"""Add identity, session, RBAC, API token, and immutable audit tables.

Revision ID: 0003_auth_foundation
Revises: 0002_legacy_schema_convergence
Create Date: 2026-07-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_auth_foundation"
down_revision = "0002_legacy_schema_convergence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_provider",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("provider_type", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("secrets_encrypted", sa.JSON(), nullable=False),
        sa.Column("group_role_mapping", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider_key", name="uq_identity_provider_provider_key"),
    )
    op.create_index("ix_identity_provider_provider_key", "identity_provider", ["provider_key"])
    op.create_index("ix_identity_provider_provider_type", "identity_provider", ["provider_type"])
    op.create_index("ix_identity_provider_enabled", "identity_provider", ["enabled"])

    op.create_table(
        "user_account",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("is_emergency", sa.Boolean(), nullable=False),
        sa.Column("password_hash", sa.Text()),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_account_username", "user_account", ["username"])
    op.execute("CREATE UNIQUE INDEX uq_user_account_username_ci ON user_account (lower(username))")
    op.create_index("ix_user_account_email", "user_account", ["email"])
    op.create_index("ix_user_account_active", "user_account", ["active"])

    op.create_table(
        "external_identity",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("identity_provider.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("username_snapshot", sa.String(160)),
        sa.Column("email_snapshot", sa.String(320)),
        sa.Column("claims_snapshot", sa.JSON(), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider_id", "subject", name="uq_external_identity_provider_subject"),
    )
    op.create_index("ix_external_identity_user_id", "external_identity", ["user_id"])
    op.create_index("ix_external_identity_provider_id", "external_identity", ["provider_id"])

    op.create_table(
        "role_binding",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("identity_provider.id", ondelete="CASCADE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_role_binding_user_id", "role_binding", ["user_id"])
    op.create_index("ix_role_binding_role", "role_binding", ["role"])
    op.create_index("ix_role_binding_provider_id", "role_binding", ["provider_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_role_binding_manual ON role_binding (user_id, role) "
        "WHERE provider_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_role_binding_provider ON role_binding (user_id, role, provider_id) "
        "WHERE provider_id IS NOT NULL"
    )

    op.create_table(
        "auth_session",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("identity_provider.id", ondelete="SET NULL")),
        sa.Column("csrf_token_hash", sa.String(64), nullable=False),
        sa.Column("client_ip_hash", sa.String(64)),
        sa.Column("user_agent_hash", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])
    op.create_index("ix_auth_session_provider_id", "auth_session", ["provider_id"])
    op.create_index("ix_auth_session_expires_at", "auth_session", ["expires_at"])
    op.create_index("ix_auth_session_revoked_at", "auth_session", ["revoked_at"])
    op.create_index("idx_auth_session_user_active", "auth_session", ["user_id", "revoked_at", "expires_at"])

    op.create_table(
        "api_token",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_prefix", sa.String(20), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_prefix", name="uq_api_token_prefix"),
        sa.UniqueConstraint("secret_hash", name="uq_api_token_secret_hash"),
    )
    op.create_index("ix_api_token_token_prefix", "api_token", ["token_prefix"])
    op.create_index("ix_api_token_active", "api_token", ["active"])
    op.create_index("ix_api_token_expires_at", "api_token", ["expires_at"])

    op.create_table(
        "security_audit_event",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("user_account.id", ondelete="SET NULL")),
        sa.Column("actor_session_id", sa.String(64)),
        sa.Column("request_id", sa.String(80)),
        sa.Column("target_type", sa.String(80)),
        sa.Column("target_id", sa.String(160)),
        sa.Column("source_ip_hash", sa.String(64)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("previous_event_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_hash", name="uq_security_audit_event_hash"),
    )
    for column in (
        "event_type",
        "outcome",
        "actor_user_id",
        "actor_session_id",
        "request_id",
        "target_type",
        "target_id",
        "event_hash",
        "created_at",
    ):
        op.create_index(f"ix_security_audit_event_{column}", "security_audit_event", [column])

    op.execute(
        """
        CREATE FUNCTION reject_security_audit_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'security_audit_event is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER security_audit_event_immutable
        BEFORE UPDATE OR DELETE ON security_audit_event
        FOR EACH ROW EXECUTE FUNCTION reject_security_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS security_audit_event_immutable ON security_audit_event")
    op.execute("DROP FUNCTION IF EXISTS reject_security_audit_mutation()")
    op.drop_table("security_audit_event")
    op.drop_table("api_token")
    op.drop_table("auth_session")
    op.drop_table("role_binding")
    op.drop_table("external_identity")
    op.drop_table("user_account")
    op.drop_table("identity_provider")
