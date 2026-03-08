from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from compat.feedback_memory_backfill import backfill_feedback_memories
from database import get_db

router = APIRouter(prefix="/api/compat", tags=["compat"])


@router.post("/memories/backfill-feedback")
async def backfill_legacy_feedback_memories(
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return backfill_feedback_memories(db, limit=limit)
