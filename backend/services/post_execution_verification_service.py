"""Compatibility facade for the persisted verification state machine."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from models.agenticops import ExecutionRun
from models.verification import VerificationRun
from verifications.service import verification_service


class PostExecutionVerificationService:
    async def verify_execution_readonly(self, db: Session, *, execution_id: int) -> Dict[str, Any]:
        execution = db.query(ExecutionRun).filter(ExecutionRun.id == execution_id).first()
        if execution is None:
            return {"success": False, "message": "execution_not_found"}
        run = (
            db.query(VerificationRun)
            .filter(VerificationRun.execution_run_id == execution_id)
            .order_by(VerificationRun.id.desc())
            .first()
        )
        if run is None:
            return {
                "success": False,
                "message": "verification_baseline_not_found; post-change baselines are forbidden",
            }
        result = await verification_service.evaluate(db, run, execution_run_id=execution_id)
        db.commit()
        return result


post_execution_verification_service = PostExecutionVerificationService()
