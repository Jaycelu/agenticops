from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from adapters.elk_adapter import elk_adapter
from adapters.zabbix_adapter import zabbix_adapter
from models.verification import BaselineSnapshot, VerificationRun
from verifications.schemas import CheckDefinition, VerificationPolicy


def matching_zabbix_alerts(alerts: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
    event_id = str(target.get("event_id") or "")
    name = str(target.get("name_contains") or "").lower()
    matches = []
    for alert in alerts:
        candidate_id = str(alert.get("eventid") or alert.get("event_id") or alert.get("objectid") or "")
        candidate_name = str(alert.get("name") or alert.get("description") or "").lower()
        if (event_id and candidate_id == event_id) or (name and name in candidate_name):
            matches.append(alert)
    return matches


class BaselineService:
    async def capture(
        self,
        db: Session,
        *,
        execution_job_id: int,
        case_id: int,
        action_index: int,
        policy_payload: dict[str, Any],
    ) -> VerificationRun:
        policy = VerificationPolicy.model_validate(policy_payload)
        run = VerificationRun(
            execution_job_id=execution_job_id,
            case_id=case_id,
            action_index=action_index,
            policy=policy.model_dump(mode="json"),
            status="baseline_collecting",
            rounds_completed=0,
        )
        db.add(run)
        db.flush()
        errors: list[str] = []
        for check in policy.checks:
            value, error = await self._collect(check)
            if error:
                errors.append(f"{check.check_id}:{error}")
                continue
            if check.kind == "zabbix_alert_absent" and not value.get("matching_alert_ids"):
                errors.append(f"{check.check_id}:originating_alert_not_present_in_baseline")
                continue
            db.add(
                BaselineSnapshot(
                    verification_run_id=run.id,
                    check_id=check.check_id,
                    target_key=self._target_key(check),
                    value=value,
                    source_collected_at=datetime.now(timezone.utc),
                )
            )
        if errors:
            run.status = "baseline_failed"
            run.verdict_reason = ";".join(errors)[:4000]
            run.finished_at = datetime.now(timezone.utc)
        else:
            run.status = "baseline_ready"
        db.flush()
        return run

    async def _collect(self, check: CheckDefinition) -> tuple[dict[str, Any], str | None]:
        if check.kind == "zabbix_alert_absent":
            result = await zabbix_adapter.get_recent_alerts(host=str(check.target["host"]), limit=100)
            if not result.get("success"):
                return {}, str(result.get("error") or "zabbix_unavailable")
            alerts = list(result.get("alerts") or [])
            matches = matching_zabbix_alerts(alerts, check.target)
            return {
                "total_alerts": len(alerts),
                "matching_alert_ids": [
                    str(item.get("eventid") or item.get("event_id") or item.get("objectid") or "") for item in matches
                ],
            }, None
        result = await elk_adapter.collect_logs(
            query=str(check.target["query"]), time_range=str(check.target.get("time_range") or "-15m,now"), limit=1000
        )
        if not result.get("success"):
            return {}, str(result.get("error") or "elk_unavailable")
        return {"count": len(result.get("logs") or [])}, None

    @staticmethod
    def _target_key(check: CheckDefinition) -> str:
        return f"{check.kind}:{check.target}"[:512]


baseline_service = BaselineService()
