from __future__ import annotations

import uuid

from pipelines.schemas import PipelineState
from models.agenticops import CaseStatus
from services.case_state_service import case_state_service


class StateFinalizer:
    def finalize(self, state: PipelineState) -> None:
        case = state.case
        if state.critic_decision == "rejected":
            target = CaseStatus.ESCALATED
            phase = "safety_escalated"
        else:
            target = CaseStatus.PLANNED if state.remediation_plan else CaseStatus.INVESTIGATING
            phase = "remediation_draft" if state.remediation_plan else "analysis"
        case_state_service.transition(
            state.db,
            case_id=case.id,
            to_state=target,
            trigger_type="legacy_pipeline",
            trigger_id=str(state.extras.get("playbook_id") or "unknown"),
            reason="legacy pipeline finalizer compatibility transition",
            idempotency_key=f"legacy-finalizer:{case.id}:{len(state.runs)}:{target.value}",
            correlation_id=str(uuid.uuid4()),
            phase=phase,
        )
        state.db.commit()
        state.db.refresh(case)


state_finalizer = StateFinalizer()
