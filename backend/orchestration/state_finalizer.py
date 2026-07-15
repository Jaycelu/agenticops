from __future__ import annotations

from datetime import datetime

from pipelines.schemas import PipelineState
from models.agenticops import CaseStatus


class StateFinalizer:
    def finalize(self, state: PipelineState) -> None:
        case = state.case
        if state.critic_decision == "rejected":
            case.status = CaseStatus.ESCALATED
            case.current_phase = "safety_escalated"
        else:
            case.status = CaseStatus.PLANNED if state.remediation_plan else CaseStatus.INVESTIGATING
            case.current_phase = "remediation_draft" if state.remediation_plan else "analysis"
        case.last_activity_at = datetime.utcnow()
        state.db.commit()
        state.db.refresh(case)


state_finalizer = StateFinalizer()
