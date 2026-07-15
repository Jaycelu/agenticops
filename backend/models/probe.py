from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func

from database import Base


class DeviceHostKey(Base):
    __tablename__ = "device_host_key"

    id = Column(BigInteger, primary_key=True)
    netbox_device_id = Column(Integer, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=22)
    algorithm = Column(String(80), nullable=False)
    public_key_base64 = Column(Text, nullable=False)
    fingerprint_sha256 = Column(String(120), nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    verified_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="RESTRICT"), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("uq_device_host_key_active", "netbox_device_id", "port", unique=True, postgresql_where=active.is_(True)),
    )


class ProbeTemplateVersion(Base):
    __tablename__ = "probe_template_version"

    id = Column(BigInteger, primary_key=True)
    probe_id = Column(String(120), nullable=False, index=True)
    version = Column(String(40), nullable=False)
    catalog_hash = Column(String(64), nullable=False)
    definition = Column(JSON, nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("uq_probe_template_version", "probe_id", "version", unique=True),)


class ProbeRun(Base):
    __tablename__ = "probe_run"

    id = Column(BigInteger, primary_key=True)
    probe_id = Column(String(120), nullable=False, index=True)
    template_version = Column(String(40), nullable=False)
    netbox_device_id = Column(Integer, nullable=False, index=True)
    credential_id = Column(Integer, ForeignKey("ssh_credential.id", ondelete="RESTRICT"), nullable=False, index=True)
    requested_by_user_id = Column(BigInteger, ForeignKey("user_account.id", ondelete="SET NULL"), index=True)
    requested_by_session_id = Column(String(64), index=True)
    status = Column(String(30), nullable=False, index=True)
    request_parameters = Column(JSON, nullable=False, default=dict)
    rendered_commands = Column(JSON, nullable=False, default=list)
    evidence = Column(JSON, nullable=False, default=dict)
    error_code = Column(String(80))
    error_detail = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_probe_run_device_running",
            "netbox_device_id",
            unique=True,
            postgresql_where=(status == "running"),
        ),
        Index("idx_probe_run_device_started", "netbox_device_id", "started_at"),
    )
