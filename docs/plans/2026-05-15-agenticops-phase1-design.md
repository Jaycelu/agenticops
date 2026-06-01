# AgenticOps Phase 1 Design

Date: 2026-05-15

## Scope

Phase 1 implements the smallest safe execution loop on top of the existing AgenticOps backend:

1. Tool Registry: a single catalog for executable capabilities and their risk constraints.
2. Policy Guard: a five-gate decision layer before any action runs.
3. Execution Service: plan-level orchestration from `RemediationPlan` to `ExecutionRun`.
4. Fabric API: an explicit endpoint to execute an approved or read-only plan.
5. Focused tests for registry loading, guard decisions, and execution-run creation.

This phase does not rebuild the agent runtime, evidence model, or pipeline engine. Those already exist in `backend/engines`, `backend/harness`, `backend/agents`, and `backend/models/agenticops.py`.

## Design Decisions

The initial implementation uses `backend/tools/catalog.json` instead of YAML. The current backend dependency set does not include `PyYAML`, and a JSON catalog is enough for the first production-safe slice.

The guard is authoritative for safety. Existing hard-coded remediation checks remain conservative, but execution approval, observe-only blocking, blacklist detection, and circuit breaking happen in `PolicyGuard`.

Only low-risk and explicitly read-only actions can execute without approval. High-risk or mutating actions create a failed `ExecutionRun` with a full audit trail when blocked.

SSH configuration changes are not enabled by default. SSH read-only actions are represented in the catalog and can be validated by the guard, but Phase 1 execution uses existing generic executors first. This avoids accidental network-device mutation while the execution loop is introduced.

## Components

### `backend/tools/base.py`

Defines `ToolRequest` and `ToolResult`, the stable request/result contract used by policy and execution services.

### `backend/tools/registry.py`

Loads `catalog.json` into `ToolSpec` objects. It supports lookup by `tool_id`, action-type fallback mapping, allowed command checks, blocked pattern checks, and basic required-field validation from a lightweight parameter schema.

### `backend/policies/schemas.py`

Defines `RiskLevel`, `GateResult`, and `PolicyDecision`. `PolicyDecision.audit` is serializable and is stored on every `ExecutionRun.audit_trail`.

### `backend/policies/guard.py`

Runs five gates:

1. Tool and parameter schema.
2. Context rule capture.
3. Effective risk calculation.
4. Approval requirement.
5. Observe-only and circuit-breaker enforcement.

The guard reads automation mode through `automation_settings_service`, falling back to `settings.automation_observe_only`.

### `backend/services/execution_service.py`

Loads a plan, converts each `recommended_actions` entry into a `ToolRequest`, calls `PolicyGuard`, creates an `ExecutionRun` for both allowed and blocked actions, runs allowed actions through `execution_engine`, and updates plan/case status.

Allowed successful runs trigger the existing `post_execution_verification_service.verify_execution_readonly`.

### Fabric API

`POST /api/fabric/plans/{plan_id}/execute` calls `execution_service.execute_plan` and returns a summary containing execution ids and per-action policy outcomes.

## Action Mapping

Phase 1 accepts explicit `tool_id` on an action. When absent, it maps existing recommendation fields conservatively:

- `mode=notify` or `action_type=notification` -> `notify.dingtalk`
- `mode=api` or `action_type=api_request` -> `api.request`
- `mode=script` or `action_type=script_run` -> `script.run`
- `mode=manual_check`, `queue_priority`, or unknown -> `manual.review`

`manual.review` is registered as non-executable. It records audit and keeps the plan safe without pretending manual recommendations were automatically remediated.

## Status Rules

Plan execution starts by setting:

- `RemediationPlan.status = EXECUTING`
- `CaseRecord.status = EXECUTING`

After all actions:

- any allowed success: `RemediationPlan.status = SUCCEEDED`, `CaseRecord.status = VERIFYING`
- only manual/blocked actions: `RemediationPlan.status = FAILED`, `CaseRecord.status = ESCALATED`
- executor failure: `RemediationPlan.status = FAILED`, `CaseRecord.status = ESCALATED`

This is intentionally strict. Later phases can introduce partial success and operator queues.

## Testing

Tests cover:

- catalog load and lookup
- blacklist risk escalation
- approval-required rejection
- observe-only rejection for mutating actions
- circuit-breaker rejection
- execution service creates `ExecutionRun` for blocked actions
- execution service can run a notification-style executor with a mocked engine

Database-heavy integration remains out of scope for this local slice unless the full Postgres stack is available.
