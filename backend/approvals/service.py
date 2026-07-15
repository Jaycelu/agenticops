from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from audit.service import security_audit_service
from auth.schemas import Principal
from config.settings import settings
from models.agenticops import RemediationPlan, RemediationPlanStatus
from models.approval import ApprovalDecision, PlanVersion


def canonical_plan_payload(plan: RemediationPlan) -> dict[str, Any]:
    return {
        "plan_id": int(plan.id),
        "case_id": int(plan.case_id),
        "plan_code": plan.plan_code,
        "execution_mode": plan.execution_mode,
        "risk_level": plan.risk_level,
        "summary": plan.summary or "",
        "plan_payload": plan.plan_payload or {},
        "rollback_payload": plan.rollback_payload or {},
        "safety_checks": plan.safety_checks or {},
    }


def plan_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ApprovalService:
    def initiate(self, db: Session, plan_id: int, principal: Principal) -> PlanVersion:
        plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).with_for_update().first()
        if plan is None:
            raise LookupError("Plan not found")
        if plan.status not in {RemediationPlanStatus.DRAFT, RemediationPlanStatus.PENDING_APPROVAL}:
            raise ValueError("only draft or pending plans can be frozen for approval")
        payload = canonical_plan_payload(plan)
        digest = plan_payload_hash(payload)
        db.query(PlanVersion).filter(
            PlanVersion.remediation_plan_id == plan.id,
            PlanVersion.state.in_(["pending", "approved"]),
        ).update({"state": "superseded"}, synchronize_session=False)
        next_version = int(
            db.query(func.coalesce(func.max(PlanVersion.version), 0)).filter(
                PlanVersion.remediation_plan_id == plan.id
            ).scalar()
            or 0
        ) + 1
        version = PlanVersion(
            remediation_plan_id=plan.id,
            version=next_version,
            plan_hash=digest,
            canonical_payload=payload,
            state="pending",
            initiated_by_user_id=principal.user_id,
            initiated_by_session_id=principal.session_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.approval_ttl_hours),
        )
        db.add(version)
        plan.status = RemediationPlanStatus.PENDING_APPROVAL
        plan.approval_status = "pending"
        db.flush()
        self._audit(db, "approval.initiated", "success", plan, version, principal)
        db.commit()
        db.refresh(version)
        return version

    def decide(
        self,
        db: Session,
        plan_id: int,
        decision: str,
        comment: str | None,
        principal: Principal,
    ) -> ApprovalDecision:
        normalized = decision.lower()
        if normalized not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        plan = db.query(RemediationPlan).filter(RemediationPlan.id == plan_id).with_for_update().first()
        if plan is None:
            raise LookupError("Plan not found")
        version = (
            db.query(PlanVersion)
            .filter(PlanVersion.remediation_plan_id == plan.id, PlanVersion.state == "pending")
            .order_by(PlanVersion.version.desc())
            .with_for_update()
            .first()
        )
        if version is None:
            raise ValueError("no pending frozen plan version")
        now = datetime.now(timezone.utc)
        if version.expires_at <= now:
            version.state = "expired"
            plan.status = RemediationPlanStatus.DRAFT
            plan.approval_status = "expired"
            db.commit()
            raise ValueError("approval request expired")
        if plan_payload_hash(canonical_plan_payload(plan)) != version.plan_hash:
            version.state = "superseded"
            plan.status = RemediationPlanStatus.DRAFT
            plan.approval_status = "invalidated"
            db.commit()
            raise ValueError("plan changed after approval initiation")
        record = ApprovalDecision(
            plan_version_id=version.id,
            decision=normalized,
            comment=(comment or "")[:4000],
            decided_by_user_id=principal.user_id,
            decided_by_session_id=principal.session_id,
            decided_plan_hash=version.plan_hash,
        )
        db.add(record)
        version.state = normalized
        version.decided_at = now
        plan.approval_status = normalized
        plan.status = RemediationPlanStatus.APPROVED if normalized == "approved" else RemediationPlanStatus.CANCELLED
        plan.approved_at = now if normalized == "approved" else None
        db.flush()
        self._audit(db, "approval.decided", "success", plan, version, principal, {"decision": normalized})
        db.commit()
        db.refresh(record)
        return record

    def active_approved_version(self, db: Session, plan: RemediationPlan, *, lock: bool = False) -> PlanVersion:
        query = db.query(PlanVersion).filter(
            PlanVersion.remediation_plan_id == plan.id,
            PlanVersion.state == "approved",
        ).order_by(PlanVersion.version.desc())
        if lock:
            query = query.with_for_update()
        version = query.first()
        if version is None:
            raise ValueError("plan has no approved frozen version")
        if version.expires_at <= datetime.now(timezone.utc):
            version.state = "expired"
            plan.approval_status = "expired"
            plan.status = RemediationPlanStatus.DRAFT
            db.flush()
            raise ValueError("approval expired")
        if plan_payload_hash(canonical_plan_payload(plan)) != version.plan_hash:
            version.state = "superseded"
            plan.approval_status = "invalidated"
            plan.status = RemediationPlanStatus.DRAFT
            db.flush()
            raise ValueError("approved plan hash mismatch")
        return version

    @staticmethod
    def history(db: Session, plan_id: int) -> list[dict[str, Any]]:
        rows = (
            db.query(PlanVersion, ApprovalDecision)
            .outerjoin(ApprovalDecision, ApprovalDecision.plan_version_id == PlanVersion.id)
            .filter(PlanVersion.remediation_plan_id == plan_id)
            .order_by(PlanVersion.version.desc())
            .all()
        )
        return [
            {
                "version": version.version,
                "plan_hash": version.plan_hash,
                "state": version.state,
                "expires_at": version.expires_at,
                "decision": decision.decision if decision else None,
                "comment": decision.comment if decision else None,
                "decided_by_user_id": decision.decided_by_user_id if decision else None,
                "decided_at": decision.created_at if decision else None,
            }
            for version, decision in rows
        ]

    @staticmethod
    def _audit(
        db: Session,
        event_type: str,
        outcome: str,
        plan: RemediationPlan,
        version: PlanVersion,
        principal: Principal,
        extra: dict[str, Any] | None = None,
    ) -> None:
        security_audit_service.append(
            db,
            event_type=event_type,
            outcome=outcome,
            actor_user_id=principal.user_id,
            actor_session_id=principal.session_id,
            target_type="plan_version",
            target_id=str(version.id),
            details={
                "plan_id": int(plan.id),
                "version": version.version,
                "plan_hash": version.plan_hash,
                **(extra or {}),
            },
        )


approval_service = ApprovalService()
