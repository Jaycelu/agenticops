from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from api.schemas.memories import MemoryEntryResponse, MemoryListResponse, MemoryOverviewResponse
from models.agenticops import MemoryEntry, MemoryType

router = APIRouter(prefix="/api/memories", tags=["记忆中心"])


@router.get("/overview", response_model=MemoryOverviewResponse)
async def get_memory_overview(db: Session = Depends(get_db)):
    total_memories = db.query(func.count(MemoryEntry.id)).scalar() or 0
    rows = db.query(MemoryEntry.memory_type, func.count(MemoryEntry.id)).group_by(MemoryEntry.memory_type).all()
    by_type = {
        (memory_type.value if hasattr(memory_type, "value") else str(memory_type)): count
        for memory_type, count in rows
    }
    high_confidence_patterns = db.query(func.count(MemoryEntry.id)).filter(
        MemoryEntry.memory_type == MemoryType.PATTERN,
        MemoryEntry.confidence >= 0.8,
    ).scalar() or 0
    successful_outcomes = db.query(func.count(MemoryEntry.id)).filter(
        MemoryEntry.memory_type == MemoryType.OUTCOME,
        MemoryEntry.success_score >= 0.8,
    ).scalar() or 0
    return MemoryOverviewResponse(
        total_memories=total_memories,
        by_type=by_type,
        high_confidence_patterns=high_confidence_patterns,
        successful_outcomes=successful_outcomes,
    )


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    memory_type: Optional[str] = None,
    case_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(MemoryEntry)
    if memory_type:
        query = query.filter(MemoryEntry.memory_type == memory_type)
    if case_id is not None:
        query = query.filter(MemoryEntry.case_id == case_id)

    total = query.count()
    items = query.order_by(MemoryEntry.created_at.desc()).offset(skip).limit(limit).all()
    return MemoryListResponse(
        total=total,
        items=[
            MemoryEntryResponse(
                id=item.id,
                case_id=item.case_id,
                memory_type=item.memory_type.value if hasattr(item.memory_type, "value") else str(item.memory_type),
                memory_key=item.memory_key,
                title=item.title,
                summary=item.summary,
                source=item.source,
                tags=item.tags or [],
                confidence=float(item.confidence or 0.0),
                success_score=float(item.success_score or 0.0),
                content=item.content or {},
                last_accessed_at=item.last_accessed_at,
                created_at=item.created_at,
            )
            for item in items
        ],
    )


@router.get("/{memory_id}", response_model=MemoryEntryResponse)
async def get_memory(memory_id: int, db: Session = Depends(get_db)):
    item = db.query(MemoryEntry).filter(MemoryEntry.id == memory_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryEntryResponse(
        id=item.id,
        case_id=item.case_id,
        memory_type=item.memory_type.value if hasattr(item.memory_type, "value") else str(item.memory_type),
        memory_key=item.memory_key,
        title=item.title,
        summary=item.summary,
        source=item.source,
        tags=item.tags or [],
        confidence=float(item.confidence or 0.0),
        success_score=float(item.success_score or 0.0),
        content=item.content or {},
        last_accessed_at=item.last_accessed_at,
        created_at=item.created_at,
    )
