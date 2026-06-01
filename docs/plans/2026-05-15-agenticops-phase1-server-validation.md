# AgenticOps Phase 1 Server Validation Runbook

Date: 2026-05-15

Use this runbook after pulling the Phase 1 code on a server that has the real backend dependencies and database access.

## 1. Preflight

From the repository root:

```bash
cd backend
pytest
```

Expected:

- all tests pass
- warnings are acceptable if they match local warnings for pytest config, Pydantic, or SQLAlchemy deprecations

Confirm the backend starts and registers executors:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Expected log signal:

```text
Execution components registered: ['api', 'notification', 'script']
```

## 2. Confirm Automation Mode

Check current automation mode:

```bash
curl -s http://127.0.0.1:8000/api/settings/automation-mode | jq
```

For the first validation, keep observe-only enabled. Phase 1 should still allow notifications but block mutating actions.

## 3. Pick a Plan

List plans:

```bash
curl -s 'http://127.0.0.1:8000/api/fabric/plans?limit=20' | jq '.items[] | {id, plan_code, status, approval_status, execution_mode, actions: (.plan_payload.recommended_actions // [] | length)}'
```

Choose a plan with at least one `recommended_actions` item.

If the plan is high-risk or pending approval, record the current state before any decision:

```bash
curl -s http://127.0.0.1:8000/api/fabric/plans/<PLAN_ID> | jq
```

## 4. Validate Safe Blocking

Execute the plan:

```bash
curl -s -X POST http://127.0.0.1:8000/api/fabric/plans/<PLAN_ID>/execute \
  -H 'Content-Type: application/json' \
  -d '{"triggered_by":"server-validation"}' | jq
```

Expected for manual or mutating actions in observe-only:

- response `success` is `false`
- each blocked action has `status = failed`
- `blocked_reason` is one of:
  - `tool_not_executable`
  - `approval_required`
  - `observe_only_blocked`
  - `circuit_breaker`

Inspect the execution rows:

```bash
curl -s 'http://127.0.0.1:8000/api/fabric/executions?remediation_plan_id=<PLAN_ID>' | jq '.items[] | {id, status, executor_type, executor_name, error_message, audit: .audit_trail[0]}'
```

Expected:

- every action created an `ExecutionRun`
- `audit_trail[0].action` is `policy_guard`
- `audit_trail[0].decision.gate_results` contains schema/rules/risk/approval/runtime gates

## 5. Validate Notification Path

Use this only if the selected plan has a notification action or you can safely create a test plan with `tool_id=notify.dingtalk`.

Expected:

- `notify.dingtalk` can pass Guard in observe-only because it is risk 0
- if the webhook config is invalid or absent, executor may fail, but the failure should still be recorded as `ExecutionRun(FAILED)` with policy audit
- if the webhook is valid, execution should become `SUCCEEDED` and then call read-only verification

Inspect one execution:

```bash
curl -s http://127.0.0.1:8000/api/fabric/executions/<EXECUTION_ID> | jq
```

Expected fields:

- `request_payload.tool_id`
- `request_payload.target_id`
- `result_payload.status`
- `result_payload.post_verification` when executor succeeded
- `audit_trail[0].decision.allowed`

## 6. Validate Approval Gate

For a high-risk plan:

```bash
curl -s -X POST http://127.0.0.1:8000/api/fabric/plans/<PLAN_ID>/approval/initiate \
  -H 'Content-Type: application/json' \
  -d '{"initiator":"server-validation","risk_level":"high"}' | jq

curl -s -X POST http://127.0.0.1:8000/api/fabric/plans/<PLAN_ID>/approval/decision \
  -H 'Content-Type: application/json' \
  -d '{"approver":"server-validation","decision":"approved","comment":"Phase 1 validation"}' | jq
```

Execute again.

Expected:

- approval gate passes
- observe-only still blocks mutating actions unless automation mode is intentionally changed
- this confirms approval and observe-only are separate gates

## 7. Database Checks

Use SQL only if direct database access is available:

```sql
select id, remediation_plan_id, executor_type, status, error_message, started_at, finished_at
from execution_run
where remediation_plan_id = <PLAN_ID>
order by started_at desc;
```

Audit spot check:

```sql
select id, audit_trail
from execution_run
where remediation_plan_id = <PLAN_ID>
order by started_at desc
limit 1;
```

Expected:

- audit JSON includes the full policy decision
- blocked actions still have rows
- failed executor calls include `error_message`

## 8. Stop Criteria

Stop and investigate before enabling broader execution if any of these happen:

- mutating action runs while observe-only is enabled
- high-risk action runs without approval
- `ExecutionRun` is not created for a blocked action
- `audit_trail` is empty
- plan status changes but no execution rows exist

## 9. Current Phase 1 Limits

- SSH read-only tools are registered and guarded but not enabled for real SSH execution in this slice.
- `ssh.config_change` is intentionally non-executable.
- Manual recommendations become auditable blocked/manual execution records, not automatic remediation.
- Full ELK/Zabbix/NetBox verification depends on server-side integration configuration.
