# AgenticOps Phase 1 Implementation Plan

Date: 2026-05-15

## Step 1: Tool Contracts and Catalog

- Add `backend/tools/__init__.py`.
- Add `backend/tools/base.py`.
- Add `backend/tools/registry.py`.
- Add `backend/tools/catalog.json`.
- Keep catalog entries conservative:
  - `manual.review`
  - `notify.dingtalk`
  - `api.request`
  - `script.run`
  - `ssh.show_command`
  - `ssh.config_change`

Validation:

- Unit test catalog loading.
- Unit test required parameter validation.

## Step 2: Policy Guard

- Add `backend/policies/__init__.py`.
- Add `backend/policies/schemas.py`.
- Add `backend/policies/rules.py`.
- Add `backend/policies/guard.py`.
- Add circuit-breaker constants to `backend/config/pipeline_thresholds.py`.

Validation:

- Unit test unregistered tools.
- Unit test blacklisted commands.
- Unit test approval gates.
- Unit test observe-only behavior.
- Unit test circuit breaker count.

## Step 3: Execution Service

- Add `backend/services/execution_service.py`.
- Implement `execute_plan(db, plan_id, triggered_by="operator")`.
- Implement action-to-tool mapping.
- Create `ExecutionRun` for every action, including blocked actions.
- Store policy audit in `ExecutionRun.audit_trail`.
- Run allowed executable actions through `execution_engine.execute_action`.
- Trigger `post_execution_verification_service` only for succeeded runs.

Validation:

- Unit test blocked action creates failed `ExecutionRun`.
- Unit test allowed action calls execution engine and records result.

## Step 4: Fabric API

- Extend `backend/api/schemas/fabric.py` with execute request/response models.
- Add `POST /api/fabric/plans/{plan_id}/execute` in `backend/api/fabric.py`.

Validation:

- Import/API schema tests through normal pytest import path.

## Step 5: Executor Registration

- Update `backend/main.py` lifespan startup to register:
  - `api_executor`
  - `notification_executor`
  - `script_executor`
- Make registration idempotent.

Validation:

- Import `main` in tests without requiring service startup.

## Step 6: Remediation Metadata

- Update `backend/agents/autonomous_remediation_agent.py` to include guard-oriented metadata in `safety_checks`.
- Update `backend/engines/case_orchestrator.py` plan creation to preserve `policy_audit`.

Validation:

- Existing pipeline tests still pass.

## Step 7: Run Tests

Run from `backend/`:

```bash
pytest
```

If full test suite requires unavailable external services, run the focused tests:

```bash
pytest tests/test_policy_guard.py tests/test_execution_service.py tests/test_pipeline_end_to_end.py
```

## Rollback Plan

The change is additive. If anything fails in integration:

- Remove the execute endpoint from `api/fabric.py`.
- Leave registry and guard modules in place; they are inert without the endpoint.
- Existing case generation and remediation plan generation continue to work because no existing route depends on `execution_service`.
