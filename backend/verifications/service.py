from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import or_

from adapters.elk_adapter import elk_adapter
from adapters.zabbix_adapter import zabbix_adapter
from models.agenticops import CaseRecord, CaseStatus, ExecutionRun, ExecutionRunStatus
from services.case_state_service import case_state_service
import uuid
from models.verification import BaselineSnapshot, VerificationCheck, VerificationRun
from verifications.baseline import matching_zabbix_alerts
from verifications.schemas import CheckDefinition, CheckResult, VerificationPolicy
from webhooks.service import webhook_service
from database import SessionLocal


class VerificationService:
    async def run_due_once(self) -> bool:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            run = (
                db.query(VerificationRun)
                .filter(
                    or_(
                        (VerificationRun.status == "pending") & (VerificationRun.next_check_at <= now),
                        (VerificationRun.status == "checking") & (VerificationRun.next_check_at <= now),
                    )
                )
                .order_by(VerificationRun.next_check_at, VerificationRun.id)
                .with_for_update(skip_locked=True)
                .first()
            )
            if run is None:
                db.rollback()
                return False
            run.status = "checking"
            run.next_check_at = now + timedelta(minutes=5)
            run_id = int(run.id)
            db.commit()
        finally:
            db.close()
        db = SessionLocal()
        try:
            run = db.query(VerificationRun).filter(VerificationRun.id == run_id).first()
            await self.evaluate(db, run, execution_run_id=run.execution_run_id)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def evaluate(
        self,
        db: Session,
        run: VerificationRun,
        *,
        execution_run_id: int | None = None,
    ) -> dict[str, Any]:
        run = db.query(VerificationRun).filter(VerificationRun.id == run.id).with_for_update().one()
        if run.status in {"verified", "regressed"}:
            return self.view(run, [])
        if execution_run_id:
            run.execution_run_id = execution_run_id
        policy = VerificationPolicy.model_validate(run.policy)
        baselines = {
            row.check_id: row
            for row in db.query(BaselineSnapshot).filter(BaselineSnapshot.verification_run_id == run.id).all()
        }
        if len(baselines) != len(policy.checks):
            run.status = "inconclusive"
            run.verdict_reason = "baseline incomplete"
            run.finished_at = datetime.now(timezone.utc)
            db.flush()
            return self.view(run, [])
        round_number = run.rounds_completed + 1
        results: list[CheckResult] = []
        for definition in policy.checks:
            results.append(await self._evaluate_check(definition, baselines[definition.check_id], round_number, policy))
        for result in results:
            baseline = baselines[result.check_id]
            db.add(
                VerificationCheck(
                    verification_run_id=run.id,
                    baseline_snapshot_id=baseline.id,
                    check_id=result.check_id,
                    round_number=round_number,
                    verdict=result.verdict,
                    observed=result.observed,
                    freshness_seconds=int(result.freshness_seconds),
                    reason=result.reason,
                )
            )
        run.rounds_completed = round_number
        verdicts = {item.verdict for item in results}
        now = datetime.now(timezone.utc)
        if verdicts == {"verified"}:
            run.status = "verified"
            run.finished_at = now
            run.verdict_reason = "all checks matched the same target and recovered"
        elif "regressed" in verdicts:
            run.status = "regressed"
            run.finished_at = now
            run.verdict_reason = "one or more target signals regressed"
        elif "inconclusive" in verdicts:
            run.status = "inconclusive"
            run.finished_at = now
            run.verdict_reason = "source unavailable, stale, or target mismatch"
        else:
            run.status = "pending"
            run.next_check_at = now + timedelta(seconds=policy.interval_seconds)
            run.verdict_reason = "recovery condition not met; another round is scheduled"
        await self._apply_case_state(db, run)
        webhook_service.enqueue(
            db,
            event_type=f"verification.{run.status}",
            aggregate_type="verification_run",
            aggregate_id=str(run.id),
            payload={
                "verification_run_id": int(run.id),
                "execution_job_id": int(run.execution_job_id),
                "case_id": int(run.case_id),
                "status": run.status,
                "round": round_number,
                "reason": run.verdict_reason,
            },
        )
        db.flush()
        return self.view(run, results)

    async def _evaluate_check(
        self,
        definition: CheckDefinition,
        baseline: BaselineSnapshot,
        round_number: int,
        policy: VerificationPolicy,
    ) -> CheckResult:
        collected_at = datetime.now(timezone.utc)
        if definition.kind == "zabbix_alert_absent":
            response = await zabbix_adapter.get_recent_alerts(host=str(definition.target["host"]), limit=100)
            if not response.get("success"):
                return self._inconclusive(definition, baseline, response.get("error") or "zabbix unavailable")
            alerts = list(response.get("alerts") or [])
            matches = matching_zabbix_alerts(alerts, definition.target)
            observed = {
                "total_alerts": len(alerts),
                "matching_alert_ids": [
                    str(item.get("eventid") or item.get("event_id") or item.get("objectid") or "") for item in matches
                ],
            }
            verdict = "verified" if not matches else "regressed" if round_number >= policy.max_rounds else "pending"
            reason = "originating alert absent" if not matches else "originating alert still present"
        else:
            response = await elk_adapter.collect_logs(
                query=str(definition.target["query"]),
                time_range=str(definition.target.get("time_range") or "-15m,now"),
                limit=1000,
            )
            if not response.get("success"):
                return self._inconclusive(definition, baseline, response.get("error") or "ELK unavailable")
            current = len(response.get("logs") or [])
            baseline_count = int((baseline.value or {}).get("count") or 0)
            threshold = baseline_count * definition.max_ratio
            observed = {"count": current, "threshold": threshold}
            verdict = "verified" if current <= threshold else "regressed" if round_number >= policy.max_rounds else "pending"
            reason = "log count reduced" if verdict == "verified" else "log count remains above threshold"
        freshness = max(0.0, (datetime.now(timezone.utc) - collected_at).total_seconds())
        return CheckResult(
            check_id=definition.check_id,
            verdict=verdict,
            baseline=baseline.value,
            observed=observed,
            freshness_seconds=freshness,
            reason=reason,
        )

    @staticmethod
    def _inconclusive(definition: CheckDefinition, baseline: BaselineSnapshot, reason: str) -> CheckResult:
        return CheckResult(
            check_id=definition.check_id,
            verdict="inconclusive",
            baseline=baseline.value,
            observed={},
            freshness_seconds=float(definition.max_age_seconds + 1),
            reason=str(reason)[:500],
        )

    @staticmethod
    async def _apply_case_state(db: Session, run: VerificationRun) -> None:
        case = db.query(CaseRecord).filter(CaseRecord.id == run.case_id).with_for_update().first()
        execution = (
            db.query(ExecutionRun).filter(ExecutionRun.id == run.execution_run_id).with_for_update().first()
            if run.execution_run_id
            else None
        )
        if run.status == "verified":
            remaining = db.query(VerificationRun.id).filter(
                VerificationRun.execution_job_id == run.execution_job_id,
                VerificationRun.id != run.id,
                VerificationRun.status != "verified",
            ).first()
            if remaining is None:
                target_state = CaseStatus.RESOLVED
                target_phase = "verified"
            else:
                target_state = CaseStatus.VERIFYING
                target_phase = "verification_pending_siblings"
            if execution:
                execution.status = ExecutionRunStatus.VERIFIED
                execution.verified_at = datetime.now(timezone.utc)
        elif run.status == "regressed":
            target_state = CaseStatus.ESCALATED
            target_phase = "verification_regressed"
            if execution:
                execution.status = ExecutionRunStatus.FAILED
        else:
            target_state = CaseStatus.VERIFYING
            target_phase = f"verification_{run.status}"
            if execution:
                execution.status = ExecutionRunStatus.VERIFYING
        case_state_service.transition(
            db,
            case_id=case.id,
            to_state=target_state,
            trigger_type="verification",
            trigger_id=str(run.id),
            reason=f"verification verdict: {run.status}",
            idempotency_key=f"verification-state:{run.id}:{run.status}:{run.rounds_completed}",
            correlation_id=str(uuid.uuid4()),
            phase=target_phase,
        )

    @staticmethod
    def view(run: VerificationRun, results: list[CheckResult]) -> dict[str, Any]:
        return {
            "success": True,
            "verification_run_id": int(run.id),
            "execution_job_id": int(run.execution_job_id),
            "case_id": int(run.case_id),
            "verdict": run.status,
            "rounds_completed": run.rounds_completed,
            "next_check_at": run.next_check_at,
            "reason": run.verdict_reason,
            "checks": [item.model_dump(mode="json") for item in results],
        }


verification_service = VerificationService()
