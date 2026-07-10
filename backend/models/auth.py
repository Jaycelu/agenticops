from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from database import Base


class IdentityProvider(Base):
    __tablename__ = "identity_provider"

    id = Column(Integer, primary_key=True)
    provider_key = Column(String(80), nullable=False, index=True)
    provider_type = Column(String(20), nullable=False, index=True)
    display_name = Column(String(120), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False, index=True)
    config = Column(JSON, nullable=False, default=dict)
    secrets_encrypted = Column(JSON, nullable=False, default=dict)
    group_role_mapping = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("provider_key", name="uq_identity_provider_provider_key"),
    )


class UserAccount(Base):
    __tablename__ = "user_account"

    id = Column(BigInteger, primary_key=True)
    username = Column(String(120), nullable=False, index=True)
    display_name = Column(String(160), nullable=False)
    email = Column(String(320), index=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    is_emergency = Column(Boolean, nullable=False, default=False)
    password_hash = Column(Text)
    password_changed_at = Column(DateTime(timezone=True))
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("uq_user_account_username_ci", func.lower(username), unique=True),
    )


class ExternalIdentity(Base):
    __tablename__ = "external_identity"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("identity_provider.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(512), nullable=False)
    username_snapshot = Column(String(160))
    email_snapshot = Column(String(320))
    claims_snapshot = Column(JSON, nullable=False, default=dict)
    last_authenticated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("provider_id", "subject", name="uq_external_identity_provider_subject"),
    )


class RoleBinding(Base):
    __tablename__ = "role_binding"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False, index=True)
    source = Column(String(30), nullable=False, default="manual")
    provider_id = Column(Integer, ForeignKey("identity_provider.id", ondelete="CASCADE"), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "uq_role_binding_manual",
            "user_id",
            "role",
            unique=True,
            postgresql_where=provider_id.is_(None),
        ),
        Index(
            "uq_role_binding_provider",
            "user_id",
            "role",
            "provider_id",
            unique=True,
            postgresql_where=provider_id.isnot(None),
        ),
    )


class AuthSession(Base):
    __tablename__ = "auth_session"

    id = Column(String(64), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("identity_provider.id", ondelete="SET NULL"), index=True)
    csrf_token_hash = Column(String(64), nullable=False)
    client_ip_hash = Column(String(64))
    user_agent_hash = Column(String(64))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_auth_session_user_active", "user_id", "revoked_at", "expires_at"),
    )


class ApiToken(Base):
    __tablename__ = "api_token"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(120), nullable=False)
    token_prefix = Column(String(20), nullable=False, index=True)
    secret_hash = Column(String(64), nullable=False)
    permissions = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True, index=True)
    expires_at = Column(DateTime(timezone=True), index=True)
    last_used_at = Column(DateTime(timezone=True))
    created_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("token_prefix", name="uq_api_token_prefix"),
        UniqueConstraint("secret_hash", name="uq_api_token_secret_hash"),
    )


class SecurityAuditEvent(Base):
    __tablename__ = "security_audit_event"

    id = Column(BigInteger, primary_key=True)
    event_type = Column(String(80), nullable=False, index=True)
    outcome = Column(String(20), nullable=False, index=True)
    actor_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"), index=True)
    actor_session_id = Column(String(64), index=True)
    request_id = Column(String(80), index=True)
    target_type = Column(String(80), index=True)
    target_id = Column(String(160), index=True)
    source_ip_hash = Column(String(64))
    details = Column(JSON, nullable=False, default=dict)
    previous_event_hash = Column(String(64))
    event_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("event_hash", name="uq_security_audit_event_hash"),
    )
