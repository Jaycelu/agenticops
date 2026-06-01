"""
Read-only post-execution verification harness (Zabbix / ELK snapshot, no mutations on targets).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from adapters.elk_adapter import elk_adapter
from adapters.zabbix_adapter import zabbix_adapter
from models.agenticops import CaseRecord, CaseStatus, ExecutionRun, ExecutionRunStatus


class PostExecutionVerificationService:
    async def verify_execution_readonly(self, db: Session, *, execution_id: int) -> Dict[str, Any]:
        run = db.query(ExecutionRun).filter(ExecutionRun.id == execution_id).first()
        if run is None:
            return {"success": False, "message": "execution_not_found"}

        case = db.query(CaseRecord).filter(CaseRecord.id == run.case_id).first()
        if case is None:
            return {"success": False, "message": "case_not_found"}

        if run.status != ExecutionRunStatus.SUCCEEDED:
            return {
                "success": False,
                "message": "execution_not_in_verifiable_state",
                "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            }

        prior = dict(run.result_payload or {})
        audit = list(run.audit_trail or [])
        started = datetime.now(timezone.utc).isoformat()

        run.status = ExecutionRunStatus.VERIFYING
        db.flush()

        host = (case.case_metadata or {}).get("zabbix_host") or case.host
        zabbix_snapshot: Dict[str, Any] = {}
        if host:
            zabbix_snapshot = await zabbix_adapter.get_recent_alerts(host=host, limit=50)

        log_snapshot: Dict[str, Any] = {}
        log_query = case.host or case.device_ip or case.title
        if log_query:
            logs_result = await elk_adapter.collect_logs(
                base_name=None,
                query=str(log_query),
                time_range="-15m,now",
                limit=80,
            )
            if logs_result.get("success"):
                log_snapshot = {"summary": elk_adapter.aggregate_logs(logs_result.get("logs") or [])}

        zcount = len((zabbix_snapshot.get("alerts") or [])) if zabbix_snapshot.get("success") else None
        verdict = "inconclusive"
        if zabbix_snapshot.get("success") and zcount == 0:
            verdict = "verified"
        elif zabbix_snapshot.get("success") and zcount is not None and zcount <= 2:
            verdict = "verified"
        elif not zabbix_snapshot.get("success") and not log_snapshot.get("summary", {}).get("devices"):
            verdict = "inconclusive"

        verification_block = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "zabbix": {"success": zabbix_snapshot.get("success"), "alert_count": zcount},
            "elk": {"has_log_summary": bool(log_snapshot.get("summary"))},
        }

        prior["verification"] = verification_block
        run.result_payload = prior

        if verdict == "verified":
            run.status = ExecutionRunStatus.VERIFIED
            run.verified_at = datetime.now(timezone.utc)
            case.status = CaseStatus.RESOLVED
            case.current_phase = "post_verify_resolved"
            case.closed_at = datetime.now(timezone.utc)
        else:
            run.status = ExecutionRunStatus.VERIFYING
            case.status = CaseStatus.VERIFYING
            case.current_phase = "post_verify_inconclusive"

        audit.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "action": "readonly_post_verify",
                "verdict": verdict,
                "execution_id": execution_id,
            }
        )
        run.audit_trail = audit
        db.commit()
        db.refresh(run)

        return {
            "success": True,
            "execution_id": run.id,
            "verdict": verdict,
            "execution_status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "case_status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "verification": verification_block,
        }


post_execution_verification_service = PostExecutionVerificationService()
