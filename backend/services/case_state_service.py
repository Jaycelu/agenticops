from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.agent_graph import CaseStateTransition
from models.agenticops import CaseRecord, CaseStatus
from observability.metrics import metrics_registry
from services.case_timeline_service import case_timeline_service


class InvalidCaseTransition(ValueError):
    pass


TERMINAL = {"resolved", "rolled_back", "escalated", "failed", "closed"}
ALLOWED: dict[str, set[str]] = {
    "new": {"normalized", "escalated", "failed"},
    "open": {"normalized", "triaged", "investigating", "planned", "failed", "escalated"},
    "normalized": {"triaged", "escalated", "failed"},
    "triaged": {"evidence_collecting", "diagnosing", "investigating", "planned", "escalated", "failed"},
    "investigating": {"evidence_collecting", "diagnosing", "planning", "escalated", "failed"},
    "evidence_collecting": {"diagnosing", "escalated", "failed"},
    "diagnosing": {"evidence_collecting", "hypothesis_review", "planning", "escalated", "failed"},
    "hypothesis_review": {"evidence_collecting", "diagnosing", "planning", "escalated", "failed"},
    "planning": {"safety_review", "awaiting_approval", "observing", "escalated", "failed"},
    "planned": {"safety_review", "awaiting_approval", "executing", "observing", "escalated", "failed"},
    "safety_review": {"awaiting_approval", "observing", "escalated", "failed"},
    "awaiting_approval": {"planning", "planned", "executing", "observing", "escalated", "failed"},
    "executing": {"verifying", "rolled_back", "escalated", "failed"},
    "verifying": {"resolved", "rolled_back", "escalated", "failed"},
    "observing": {"planning", "awaiting_approval", "resolved", "escalated", "failed"},
}


def state_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value).lower()


class CaseStateService:
    def transition(
        self,
        db: Session,
        *,
        case_id: int,
        to_state: str | CaseStatus,
        trigger_type: str,
        reason: str,
        idempotency_key: str,
        graph_run_id: str | None = None,
        trigger_id: str | None = None,
        agent_run_id: int | None = None,
        task_id: int | None = None,
        evidence_ids: list[int] | None = None,
        correlation_id: str,
        expected_from: str | None = None,
        phase: str | None = None,
    ) -> CaseStateTransition:
        prior = db.query(CaseStateTransition).filter(CaseStateTransition.idempotency_key == idempotency_key).first()
        if prior is not None:
            return prior
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).with_for_update().first()
        if case is None:
            raise LookupError("case not found")
        current = state_value(case.status)
        target = state_value(to_state)
        if expected_from and current != expected_from:
            raise InvalidCaseTransition(f"expected {expected_from}, got {current}")
        if current != target and target not in ALLOWED.get(current, set()):
            raise InvalidCaseTransition(f"illegal case transition: {current} -> {target}")
        transition = CaseStateTransition(
            case_id=case_id,
            graph_run_id=graph_run_id,
            from_state=current,
            to_state=target,
            trigger_type=trigger_type,
            trigger_id=trigger_id,
            reason=reason,
            agent_run_id=agent_run_id,
            task_id=task_id,
            evidence_ids=evidence_ids or [],
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        db.add(transition)
        if current != target:
            case.status = CaseStatus(target)
        case.current_phase = phase or target
        case.last_activity_at = datetime.now(timezone.utc)
        if target in TERMINAL:
            case.closed_at = datetime.now(timezone.utc)
        elif case.closed_at is not None:
            case.closed_at = None
        db.flush()
        case_timeline_service.append(
            db,
            case_id=case_id,
            graph_run_id=graph_run_id,
            task_id=task_id,
            event_type="case_state_transition",
            title=f"Case {current} → {target}",
            actor_type=trigger_type,
            actor_id=trigger_id,
            correlation_id=correlation_id,
            idempotency_key=f"timeline:{idempotency_key}",
            payload={"from": current, "to": target, "reason": reason, "evidence_ids": evidence_ids or []},
        )
        metrics_registry.increment("case_state_transition_total", from_state=current, to_state=target)
        return transition


case_state_service = CaseStateService()
