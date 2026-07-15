from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from approvals.service import approval_service
from audit.service import security_audit_service
from auth.schemas import Principal
from config.settings import settings
from models.agenticops import (
    CaseRecord,
    CaseStatus,
    ExecutionRun,
    ExecutionRunStatus,
    RemediationPlan,
    RemediationPlanStatus,
)
from models.execution_job import ExecutionActionResult, ExecutionJob, IdempotencyRecord
from policies.guard import PolicyGuard, policy_guard
from services.execution_engine import ExecutionStatus, ExecutorType, RetryPolicy, execution_engine
from tools.base import ToolRequest
from tools.registry import ToolSpec, tool_registry
from webhooks.service import webhook_service
from verifications.baseline import baseline_service
from verifications.service import verification_service


# Advisory tools describe human process steps, not executor invocations.
# Actions resolving to one of these are recorded as "skipped" (no ExecutionRun,
# not a failure) instead of being driven through the executor.
ADVISORY_TOOL_IDS = {"manual.review"}


class ExecutionService:
    def __init__(self, guard: Optional[PolicyGuard] = None) -> None:
        self.guard = guard or policy_guard

    async def execute_plan(
        self,
        db: Session,
        plan_id: int,
        *,
        principal: Principal,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).with_for_update().first()
        if plan is None:
            raise LookupError("Plan not found")
        case = db.query(CaseRecord).filter(CaseRecord.id == plan.case_id).first()
        if case is None:
            raise LookupError("Case not found")
        version = approval_service.active_approved_version(db, plan, lock=True)
        frozen_actions = list(
            (version.canonical_payload.get("plan_payload") or {}).get("recommended_actions") or []
        )
        if not frozen_actions:
            raise ValueError("Plan has no recommended actions")
        request_hash = hashlib.sha256(
            json.dumps(
                {"plan_id": plan_id, "plan_version_id": int(version.id), "plan_hash": version.plan_hash},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        existing = db.query(IdempotencyRecord).filter(
            IdempotencyRecord.scope == "plan.execute",
            IdempotencyRecord.idempotency_key == idempotency_key,
        ).first()
        if existing:
            if existing.request_hash != request_hash:
                raise ValueError("idempotency key was already used for a different request")
            if existing.status == "completed":
                return dict(existing.response_snapshot or {})
            raise ValueError("execution with this idempotency key is still in progress")
        prior_job = db.query(ExecutionJob).filter(ExecutionJob.plan_version_id == version.id).first()
        if prior_job:
            if prior_job.result:
                return dict(prior_job.result)
            raise ValueError("this approved plan version already has an execution job")
        job = ExecutionJob(
            plan_version_id=version.id,
            remediation_plan_id=plan.id,
            case_id=case.id,
            plan_hash=version.plan_hash,
            idempotency_key=idempotency_key,
            status="running",
            requested_by_user_id=principal.user_id,
            requested_by_session_id=principal.session_id,
            result={},
        )
        record = IdempotencyRecord(
            scope="plan.execute",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="in_progress",
            resource_type="execution_job",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.idempotency_ttl_hours),
            response_snapshot={},
        )
        db.add_all([job, record])
        db.flush()
        record.resource_id = str(job.id)
        security_audit_service.append(
            db,
            event_type="execution.accepted",
            outcome="success",
            actor_user_id=principal.user_id,
            actor_session_id=principal.session_id,
            target_type="execution_job",
            target_id=str(job.id),
            details={"plan_id": plan_id, "plan_version_id": int(version.id), "plan_hash": version.plan_hash},
        )
        webhook_service.enqueue(
            db,
            event_type="execution.accepted",
            aggregate_type="execution_job",
            aggregate_id=str(job.id),
            payload={"execution_job_id": int(job.id), "plan_id": plan_id, "case_id": int(case.id)},
        )
        db.commit()

        # Worker boundary: lock and verify the frozen hash again immediately before
        # any external side effect.
        try:
            plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).with_for_update().one()
            case = db.query(CaseRecord).filter(CaseRecord.id == plan.case_id).with_for_update().one()
            version = approval_service.active_approved_version(db, plan, lock=True)
            if version.plan_hash != job.plan_hash:
                raise ValueError("execution job plan hash mismatch")
        except Exception as exc:
            db.rollback()
            job = db.query(ExecutionJob).filter(ExecutionJob.id == job.id).with_for_update().one()
            record = db.query(IdempotencyRecord).filter(IdempotencyRecord.id == record.id).with_for_update().one()
            response = {
                "success": False,
                "plan_id": plan_id,
                "case_id": int(job.case_id),
                "status": "failed",
                "case_status": "unchanged",
                "executions": [],
                "execution_job_id": int(job.id),
            }
            job.status = "failed"
            job.error_code = type(exc).__name__[:80]
            job.result = response
            job.finished_at = datetime.now(timezone.utc)
            record.status = "completed"
            record.response_snapshot = response
            db.commit()
            return response
        actions = list((version.canonical_payload.get("plan_payload") or {}).get("recommended_actions") or [])

        plan.status = RemediationPlanStatus.EXECUTING
        case.status = CaseStatus.EXECUTING
        case.current_phase = "executing"
        db.flush()

        execution_summaries: List[Dict[str, Any]] = []
        allowed_success = False
        hard_failure = False
        verified_resolved = False
        mutation_verdicts: List[str] = []
        skipped_count = 0

        for index, action in enumerate(actions, start=1):
            request = self._build_tool_request(action, case=case, plan=plan, triggered_by=principal.username)
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
                self._record_action_result(db, job, index, request, spec, "skipped", execution_summaries[-1])
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
                self._record_action_result(db, job, index, request, spec, "failed", execution_summaries[-1])
                continue

            verification_run = None
            if spec and spec.capability == "mutation":
                verification_run = await baseline_service.capture(
                    db,
                    execution_job_id=int(job.id),
                    case_id=int(case.id),
                    action_index=index,
                    policy_payload=request.action.get("verification") or {},
                )
                if verification_run.status != "baseline_ready":
                    run.status = ExecutionRunStatus.FAILED
                    run.error_message = "mandatory verification baseline failed"
                    run.result_payload = {
                        "status": ExecutionStatus.FAILED.value,
                        "error": "verification_baseline_failed",
                        "verification_run_id": int(verification_run.id),
                    }
                    run.finished_at = datetime.now(timezone.utc)
                    hard_failure = True
                    db.flush()
                    execution_summaries.append(self._summary(run, decision.to_dict()))
                    self._record_action_result(
                        db, job, index, request, spec, "failed", {"summary": execution_summaries[-1], "result": run.result_payload}
                    )
                    continue

            result = await self._execute_allowed_action(db, run, request, spec, case=case)
            run.result_payload = result
            run.finished_at = datetime.now(timezone.utc)
            action_succeeded = result.get("status") == ExecutionStatus.SUCCESS.value
            if action_succeeded:
                run.status = ExecutionRunStatus.SUCCEEDED
                allowed_success = True
            else:
                run.status = ExecutionRunStatus.FAILED
                run.error_message = result.get("error") or result.get("message") or "execution_failed"
                hard_failure = True
            db.flush()

            if run.status == ExecutionRunStatus.SUCCEEDED and verification_run:
                verification = await verification_service.evaluate(
                    db, verification_run, execution_run_id=int(run.id)
                )
                run.result_payload = {**result, "post_verification": verification}
                mutation_verdicts.append(str(verification.get("verdict") or "inconclusive"))

            execution_summaries.append(self._summary(run, decision.to_dict()))
            self._record_action_result(
                db,
                job,
                index,
                request,
                spec,
                "succeeded" if action_succeeded else "failed",
                {"summary": execution_summaries[-1], "result": run.result_payload or {}},
            )

        verified_resolved = bool(mutation_verdicts) and all(item == "verified" for item in mutation_verdicts)
        rollback_attempted = False
        rollback_succeeded = False
        if allowed_success and hard_failure:
            rollback_actions = list(
                (version.canonical_payload.get("rollback_payload") or {}).get("recommended_actions") or []
            )
            if rollback_actions:
                rollback_attempted = True
                rollback_succeeded, rollback_summaries = await self._execute_rollback(
                    db,
                    job=job,
                    plan=plan,
                    case=case,
                    actions=rollback_actions,
                    start_index=len(actions) + 1,
                    requested_by=principal.username,
                )
                execution_summaries.extend(rollback_summaries)

        if rollback_attempted and rollback_succeeded:
            plan.status = RemediationPlanStatus.ROLLED_BACK
            case.status = CaseStatus.ESCALATED
            case.current_phase = "execution_rolled_back"
        elif rollback_attempted:
            plan.status = RemediationPlanStatus.FAILED
            case.status = CaseStatus.ESCALATED
            case.current_phase = "rollback_failed"
        elif allowed_success and not hard_failure:
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

        response = {
            "success": not hard_failure,
            "plan_id": int(plan.id),
            "case_id": int(case.id),
            "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
            "case_status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "executions": execution_summaries,
            "execution_job_id": int(job.id),
        }
        job.status = (
            "succeeded"
            if response["success"]
            else "rolled_back"
            if plan.status == RemediationPlanStatus.ROLLED_BACK
            else "failed"
        )
        job.result = response
        job.finished_at = datetime.now(timezone.utc)
        record.status = "completed"
        record.response_snapshot = response
        security_audit_service.append(
            db,
            event_type="execution.completed",
            outcome="success" if response["success"] else "failed",
            actor_user_id=principal.user_id,
            actor_session_id=principal.session_id,
            target_type="execution_job",
            target_id=str(job.id),
            details={"plan_id": plan_id, "status": job.status},
        )
        webhook_service.enqueue(
            db,
            event_type=f"execution.{job.status}",
            aggregate_type="execution_job",
            aggregate_id=str(job.id),
            payload={
                "execution_job_id": int(job.id),
                "plan_id": plan_id,
                "case_id": int(case.id),
                "status": job.status,
                "success": response["success"],
            },
        )
        db.commit()
        return response

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
        spec = tool_registry.get(tool_id)
        mode = "observe" if spec and spec.capability in {"read_only", "manual"} else "execute"
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
        db: Session,
        run: ExecutionRun,
        request: ToolRequest,
        spec: Optional[ToolSpec],
        *,
        case: CaseRecord,
    ) -> Dict[str, Any]:
        if spec is None:
            return {"status": ExecutionStatus.FAILED.value, "message": "tool spec missing", "error": "tool_spec_missing"}
        if spec.capability == "notification":
            event = webhook_service.enqueue(
                db,
                event_type="automation.notification",
                aggregate_type="execution_run",
                aggregate_id=str(run.id),
                payload={
                    "title": request.params.get("title") or "AgenticOps notification",
                    "message": request.params.get("message") or "",
                    "case_id": int(case.id),
                    "plan_id": request.plan_id,
                },
            )
            db.flush()
            return {
                "status": ExecutionStatus.SUCCESS.value,
                "message": "notification queued in webhook outbox",
                "details": {"event_id": event.event_id},
            }
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
        if case.netbox_device_id:
            action_config.setdefault("netbox_device_id", int(case.netbox_device_id))
        context = {
            "case_id": int(case.id),
            "case_code": case.case_code,
            "host": case.host,
            "device_ip": case.device_ip,
            "plan_id": request.plan_id,
            "execution_run_id": int(run.id),
        }
        retry_policy = RetryPolicy(max_retries=0) if spec.capability == "mutation" else None
        result = await execution_engine.execute_action(
            int(run.id), executor_type, action_config, context, retry_policy=retry_policy
        )
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

    async def _execute_rollback(
        self,
        db: Session,
        *,
        job: ExecutionJob,
        plan: RemediationPlan,
        case: CaseRecord,
        actions: List[Dict[str, Any]],
        start_index: int,
        requested_by: str,
    ) -> tuple[bool, List[Dict[str, Any]]]:
        summaries: List[Dict[str, Any]] = []
        all_succeeded = True
        for offset, action in enumerate(actions):
            index = start_index + offset
            request = self._build_tool_request(action, case=case, plan=plan, triggered_by=requested_by)
            spec = tool_registry.get(request.tool_id)
            decision = self.guard.check(request, case=case, plan=plan, db=db)
            run = self._create_execution_run(
                db,
                case=case,
                plan=plan,
                request=request,
                spec=spec,
                action_index=index,
                decision={**decision.to_dict(), "rollback": True},
            )
            if not decision.allowed:
                run.status = ExecutionRunStatus.FAILED
                run.error_message = decision.blocked_reason or "rollback_policy_blocked"
                result: Dict[str, Any] = {"error": run.error_message}
            else:
                result = await self._execute_allowed_action(db, run, request, spec, case=case)
                if result.get("status") == ExecutionStatus.SUCCESS.value:
                    run.status = ExecutionRunStatus.ROLLED_BACK
                else:
                    run.status = ExecutionRunStatus.FAILED
                    run.error_message = result.get("error") or result.get("message") or "rollback_failed"
            run.result_payload = {**result, "rollback": True}
            run.finished_at = datetime.now(timezone.utc)
            db.flush()
            succeeded = run.status == ExecutionRunStatus.ROLLED_BACK
            all_succeeded = all_succeeded and succeeded
            summary = {**self._summary(run, decision.to_dict()), "rollback": True}
            summaries.append(summary)
            self._record_action_result(
                db,
                job,
                index,
                request,
                spec,
                "rolled_back" if succeeded else "rollback_failed",
                {"summary": summary, "result": result},
            )
        return all_succeeded, summaries

    @staticmethod
    def _record_action_result(
        db: Session,
        job: ExecutionJob,
        index: int,
        request: ToolRequest,
        spec: Optional[ToolSpec],
        status: str,
        result: Dict[str, Any],
    ) -> None:
        request_hash = hashlib.sha256(
            json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        db.add(
            ExecutionActionResult(
                execution_job_id=job.id,
                action_index=index,
                tool_id=request.tool_id,
                capability=getattr(spec, "capability", "unknown"),
                status=status,
                request_hash=request_hash,
                result=result,
                error_message=result.get("error") or result.get("blocked_reason"),
                finished_at=datetime.now(timezone.utc),
            )
        )
        db.flush()


execution_service = ExecutionService()
