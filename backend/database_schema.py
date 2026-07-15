from __future__ import annotations

from typing import Iterable

from sqlalchemy import Table

from database import Base


def active_tables() -> list[Table]:
    """Return the production schema managed by Alembic.

    Importing the model modules registers all historical models in ``Base.metadata``.
    This explicit list prevents retired automation tables from reappearing through
    autogenerate.
    """
    from models.agenticops import (
        AgentClaim,
        AgentRun,
        CaseRecord,
        EvidenceItem,
        ExecutionRun,
        MemoryEntry,
        RemediationPlan,
        SourceEvent,
    )
    from models.automation import (
        AssetDevice,
        AutomationPolicy,
        DeviceState,
        LocalTicket,
        LogAnalysisResult,
        LogSample,
        RawAnomaly,
        SSHCredential,
        SSHCredentialDeviceBinding,
        Site,
        SiteAutomationSwitch,
    )
    from models.automation_settings import AutomationSetting
    from models.auth import (
        ApiToken,
        AuthLoginTransaction,
        AuthSession,
        ExternalIdentity,
        IdentityProvider,
        RoleBinding,
        SecurityAuditEvent,
        UserAccount,
    )
    from models.integration_settings import IntegrationSetting
    from models.log_scope import LogScope
    from models.probe import DeviceHostKey, ProbeRun, ProbeTemplateVersion

    return [
        Site.__table__,
        SiteAutomationSwitch.__table__,
        DeviceState.__table__,
        LogSample.__table__,
        LogAnalysisResult.__table__,
        AutomationPolicy.__table__,
        RawAnomaly.__table__,
        SSHCredential.__table__,
        SSHCredentialDeviceBinding.__table__,
        AssetDevice.__table__,
        SourceEvent.__table__,
        LocalTicket.__table__,
        CaseRecord.__table__,
        EvidenceItem.__table__,
        AgentRun.__table__,
        AgentClaim.__table__,
        MemoryEntry.__table__,
        RemediationPlan.__table__,
        ExecutionRun.__table__,
        IntegrationSetting.__table__,
        LogScope.__table__,
        AutomationSetting.__table__,
        IdentityProvider.__table__,
        UserAccount.__table__,
        ExternalIdentity.__table__,
        RoleBinding.__table__,
        AuthSession.__table__,
        AuthLoginTransaction.__table__,
        ApiToken.__table__,
        SecurityAuditEvent.__table__,
        DeviceHostKey.__table__,
        ProbeTemplateVersion.__table__,
        ProbeRun.__table__,
    ]


def active_table_names(tables: Iterable[Table] | None = None) -> set[str]:
    return {table.name for table in (tables or active_tables())}


def active_metadata():
    # Models are registered by active_tables(). Return the shared metadata so foreign
    # key resolution keeps working during Alembic autogenerate.
    active_tables()
    return Base.metadata
