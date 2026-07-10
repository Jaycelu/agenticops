from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    EXECUTOR = "executor"
    ADMIN = "admin"


class Permission(StrEnum):
    CASES_READ = "cases.read"
    EVIDENCE_READ = "evidence.read"
    PROBES_RUN = "probes.run"
    APPROVALS_REQUEST = "approvals.request"
    APPROVALS_DECIDE = "approvals.decide"
    EXECUTIONS_RUN = "executions.run"
    WEBHOOKS_MANAGE = "webhooks.manage"
    CREDENTIALS_MANAGE = "credentials.manage"
    INTEGRATIONS_MANAGE = "integrations.manage"
    AUTOMATION_MANAGE = "automation.manage"
    IDENTITIES_MANAGE = "identities.manage"
    USERS_MANAGE = "users.manage"
    AUDIT_READ = "audit.read"
    TOKENS_MANAGE = "tokens.manage"


READ_PERMISSIONS = {
    Permission.CASES_READ,
    Permission.EVIDENCE_READ,
}

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: set(READ_PERMISSIONS),
    Role.OPERATOR: set(READ_PERMISSIONS) | {Permission.PROBES_RUN, Permission.APPROVALS_REQUEST},
    Role.APPROVER: set(READ_PERMISSIONS) | {Permission.APPROVALS_DECIDE},
    Role.EXECUTOR: set(READ_PERMISSIONS) | {Permission.EXECUTIONS_RUN},
    Role.ADMIN: set(Permission),
}


def permissions_for_roles(roles: set[str] | frozenset[str]) -> frozenset[str]:
    permissions: set[str] = set()
    for raw_role in roles:
        try:
            role = Role(raw_role)
        except ValueError:
            continue
        permissions.update(permission.value for permission in ROLE_PERMISSIONS[role])
    return frozenset(permissions)
