from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models.agenticops import AgentClaim, AgentRun, CaseRecord, RemediationPlan, RemediationPlanStatus
from tools.registry import tool_registry


class PlanBuilder:
    def build(
        self,
        db: Session,
        case: CaseRecord,
        agent_run: AgentRun,
        claim: AgentClaim,
        payload: dict[str, Any],
    ) -> RemediationPlan:
        plan = (
            db.query(RemediationPlan)
            .filter(RemediationPlan.case_id == case.id)
            .order_by(RemediationPlan.created_at.desc())
            .first()
        )
        if plan is None:
            plan = RemediationPlan(case_id=case.id, plan_code=f"PLAN-{case.case_code}")
            db.add(plan)
            db.flush()
        actions = payload.get("recommended_actions") or []
        for action in actions:
            spec = tool_registry.get(str(action.get("tool_id") or "manual.review"))
            if spec and spec.capability == "mutation" and not action.get("verification"):
                action["verification"] = self.default_verification_policy(case)
        plan.generated_by_agent_run_id = agent_run.id
        plan.status = RemediationPlanStatus.DRAFT
        plan.execution_mode = payload.get("execution_mode") or "manual"
        plan.approval_status = payload.get("approval_status") or "required"
        plan.risk_level = case.risk_level
        plan.summary = claim.claim_text
        plan.plan_payload = {
            "recommendations": payload.get("recommendations") or [],
            "recommended_actions": actions,
            "root_cause": payload.get("root_cause"),
            "impact_scope": payload.get("impact_scope"),
            "policy_audit": payload.get("policy_audit") or {},
        }
        plan.rollback_payload = {"steps": payload.get("rollback_plan") or []}
        plan.safety_checks = {
            **(payload.get("safety_checks") or {}),
            "policy_audit": payload.get("policy_audit") or {},
        }
        return plan

    @staticmethod
    def default_verification_policy(case: CaseRecord) -> dict[str, Any]:
        source_system = (case.source_event.source_system if case.source_event else "").lower()
        raw = (case.source_event.raw_payload if case.source_event else {}) or {}
        if source_system == "zabbix":
            target = {
                "host": (case.case_metadata or {}).get("zabbix_host") or case.host or case.device_ip,
                "name_contains": case.title,
            }
            event_id = raw.get("event_id") or raw.get("eventid") or raw.get("object_id")
            if event_id:
                target["event_id"] = str(event_id)
            check = {
                "check_id": "originating-zabbix-alert",
                "kind": "zabbix_alert_absent",
                "target": target,
                "max_age_seconds": 300,
            }
        else:
            check = {
                "check_id": "originating-log-rate",
                "kind": "elk_count_reduced",
                "target": {"query": case.host or case.device_ip or case.title, "time_range": "-15m,now"},
                "max_age_seconds": 300,
                "max_ratio": 0.5,
            }
        return {"checks": [check], "max_rounds": 3, "interval_seconds": 60}


plan_builder = PlanBuilder()
