from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.agenticops import (
    CaseRecord,
    CaseStatus,
    ExecutionRun,
    ExecutionRunStatus,
    RemediationPlan,
    RemediationPlanStatus,
)
from policies.guard import PolicyGuard, policy_guard
from services.execution_engine import ExecutionStatus, ExecutorType, execution_engine
from services.post_execution_verification_service import post_execution_verification_service
from tools.base import ToolRequest
from tools.registry import ToolSpec, tool_registry


# Advisory tools describe human process steps, not executor invocations.
# Actions resolving to one of these are recorded as "skipped" (no ExecutionRun,
# not a failure) instead of being driven through the executor.
ADVISORY_TOOL_IDS = {"manual.review"}


class ExecutionService:
    def __init__(self, guard: Optional[PolicyGuard] = None) -> None:
        self.guard = guard or policy_guard

    async def execute_plan(self, db: Session, plan_id: int, *, triggered_by: str) -> Dict[str, Any]:
        plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).first()
        if plan is None:
            raise LookupError("Plan not found")

        case = db.query(CaseRecord).filter(CaseRecord.id == plan.case_id).first()
        if case is None:
            raise LookupError("Case not found")

        actions = list((plan.plan_payload or {}).get("recommended_actions") or [])
        if not actions:
            raise ValueError("Plan has no recommended actions")

        plan.status = RemediationPlanStatus.EXECUTING
        case.status = CaseStatus.EXECUTING
        case.current_phase = "executing"
        db.flush()

        execution_summaries: List[Dict[str, Any]] = []
        allowed_success = False
        hard_failure = False
        verified_resolved = False
        skipped_count = 0

        for index, action in enumerate(actions, start=1):
            request = self._build_tool_request(action, case=case, plan=plan, triggered_by=triggered_by)
            spec = tool_registry.get(request.tool_id)

            # Advisory action — record as skipped, no ExecutionRun, not a failure.
            if request.tool_id in ADVISORY_TOOL_IDS:
                skipped_count += 1
                execution_summaries.append(
                    {
                        "execution_run_id": None,
                        "tool_id": request.tool_id,
                        "status": "skipped",
                        "blocked_reason": None,
                        "allowed": True,
                        "effective_risk": int(getattr(spec, "risk_level", 0) or 0),
                    }
                )
                continue

            decision = self.guard.check(request, case=case, plan=plan, db=db)
            run = self._create_execution_run(
                db,
                case=case,
                plan=plan,
                request=request,
                spec=spec,
                action_index=index,
                decision=decision.to_dict(),
            )

            if not decision.allowed:
                run.status = ExecutionRunStatus.FAILED
                run.error_message = decision.blocked_reason or "policy_blocked"
                run.finished_at = datetime.now(timezone.utc)
                hard_failure = True
                db.flush()
                execution_summaries.append(self._summary(run, decision.to_dict()))
                continue

            result = await self._execute_allowed_action(run, request, spec, case=case)
            run.result_payload = result
            run.finished_at = datetime.now(timezone.utc)
            if result.get("status") == ExecutionStatus.SUCCESS.value:
                run.status = ExecutionRunStatus.SUCCEEDED
                allowed_success = True
            else:
                run.status = ExecutionRunStatus.FAILED
                run.error_message = result.get("error") or result.get("message") or "execution_failed"
                hard_failure = True
            db.flush()

            if run.status == ExecutionRunStatus.SUCCEEDED:
                verification = await post_execution_verification_service.verify_execution_readonly(db, execution_id=int(run.id))
                run.result_payload = {**result, "post_verification": verification}
                verified_resolved = verified_resolved or case.status == CaseStatus.RESOLVED

            execution_summaries.append(self._summary(run, decision.to_dict()))

        if allowed_success and not hard_failure:
            plan.status = RemediationPlanStatus.SUCCEEDED
            if not verified_resolved:
                case.status = CaseStatus.VERIFYING
                case.current_phase = "post_execution_verify"
        elif allowed_success:
            plan.status = RemediationPlanStatus.FAILED
            case.status = CaseStatus.VERIFYING
            case.current_phase = "post_execution_partial"
        elif hard_failure:
            plan.status = RemediationPlanStatus.FAILED
            case.status = CaseStatus.ESCALATED
            case.current_phase = "execution_blocked"
        else:
            # Only advisory / skipped actions — nothing executed, nothing failed.
            # The plan is purely advisory: revert to DRAFT, leave the case PLANNED.
            plan.status = RemediationPlanStatus.DRAFT
            case.status = CaseStatus.PLANNED
            case.current_phase = "advisory_only"

        db.commit()
        return {
            "success": not hard_failure,
            "plan_id": int(plan.id),
            "case_id": int(case.id),
            "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
            "case_status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "executions": execution_summaries,
        }

    def _build_tool_request(
        self,
        action: Dict[str, Any],
        *,
        case: CaseRecord,
        plan: RemediationPlan,
        triggered_by: str,
    ) -> ToolRequest:
        tool_id = self._resolve_tool_id(action)
        params = self._action_params(action, tool_id)
        target = {
            "case_id": int(case.id),
            "site_id": case.site_id,
            "netbox_device_id": case.netbox_device_id,
            "device_ip": case.device_ip,
            "host": case.host,
            "role": (case.case_metadata or {}).get("device_role"),
            "tags": (case.case_metadata or {}).get("tags") or [],
        }
        mode = str(action.get("tool_mode") or action.get("mode") or ("execute" if tool_id != "manual.review" else "observe"))
        if tool_id == "notify.dingtalk":
            mode = "execute"
        elif tool_id == "manual.review":
            mode = "observe"
        return ToolRequest(
            tool_id=tool_id,
            params=params,
            target=target,
            mode=mode,
            action=action,
            requested_by=triggered_by,
            case_id=int(case.id),
            plan_id=int(plan.id),
        )

    def _resolve_tool_id(self, action: Dict[str, Any]) -> str:
        explicit = action.get("tool_id")
        if explicit:
            return str(explicit)
        action_type = str(action.get("action_type") or "").lower()
        mode = str(action.get("mode") or "").lower()
        if action_type in {"notification", "notify", "dingtalk"} or mode == "notify":
            return "notify.dingtalk"
        if action_type in {"api", "api_request"} or mode == "api":
            return "api.request"
        if action_type in {"script", "script_run"} or mode == "script":
            return "script.run"
        if action_type in {"ssh_show", "ssh_show_command"}:
            return "ssh.show_command"
        if action_type in {"ssh_config", "ssh_config_change"}:
            return "ssh.config_change"
        return "manual.review"

    def _action_params(self, action: Dict[str, Any], tool_id: str) -> Dict[str, Any]:
        params = dict(action.get("params") or {})
        for key in (
            "url",
            "method",
            "headers",
            "body",
            "message",
            "title",
            "webhook_url",
            "notification_type",
            "script_path",
            "script_args",
            "commands",
            "command",
            "credential_id",
            "netbox_device_id",
        ):
            if key in action and key not in params:
                params[key] = action[key]
        if tool_id == "notify.dingtalk":
            params.setdefault("notification_type", "dingtalk")
            params.setdefault("message", action.get("reason") or action.get("title") or "AgenticOps notification")
        return params

    def _create_execution_run(
        self,
        db: Session,
        *,
        case: CaseRecord,
        plan: RemediationPlan,
        request: ToolRequest,
        spec: Optional[ToolSpec],
        action_index: int,
        decision: Dict[str, Any],
    ) -> ExecutionRun:
        target_id = request.target.get("netbox_device_id") or request.target.get("device_ip") or request.target.get("host")
        run = ExecutionRun(
            case_id=case.id,
            remediation_plan_id=plan.id,
            executor_type=getattr(spec, "executor_type", "unknown"),
            executor_name=getattr(spec, "name", request.tool_id),
            status=ExecutionRunStatus.RUNNING,
            command_summary=request.action.get("title") or request.action.get("action_type") or request.tool_id,
            request_payload={
                **request.to_dict(),
                "action_index": action_index,
                "target_id": str(target_id) if target_id is not None else None,
            },
            result_payload={},
            audit_trail=[{"action": "policy_guard", "decision": decision}],
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()
        return run

    async def _execute_allowed_action(
        self,
        run: ExecutionRun,
        request: ToolRequest,
        spec: Optional[ToolSpec],
        *,
        case: CaseRecord,
    ) -> Dict[str, Any]:
        if spec is None:
            return {"status": ExecutionStatus.FAILED.value, "message": "tool spec missing", "error": "tool_spec_missing"}
        try:
            executor_type = ExecutorType(spec.executor_type)
        except ValueError:
            return {
                "status": ExecutionStatus.FAILED.value,
                "message": f"Unsupported executor type: {spec.executor_type}",
                "error": "unsupported_executor_type",
            }

        action_config = dict(request.params)
        action_config.setdefault("timeout", spec.timeout)
        action_config.setdefault("read_only", request.mode == "observe" and request.tool_id != "script.run")
        context = {
            "case_id": int(case.id),
            "case_code": case.case_code,
            "host": case.host,
            "device_ip": case.device_ip,
            "plan_id": request.plan_id,
            "execution_run_id": int(run.id),
        }
        result = await execution_engine.execute_action(int(run.id), executor_type, action_config, context)
        return result.to_dict()

    def _summary(self, run: ExecutionRun, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "execution_run_id": int(run.id),
            "tool_id": (run.request_payload or {}).get("tool_id"),
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "blocked_reason": decision.get("blocked_reason"),
            "allowed": decision.get("allowed"),
            "effective_risk": decision.get("effective_risk"),
        }


execution_service = ExecutionService()
