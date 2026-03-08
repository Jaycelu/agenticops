from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from models.agenticops import MemoryEntry, MemoryType


class MemoryIngestionService:
    def upsert_memory(
        self,
        db: Session,
        *,
        memory_type: MemoryType,
        memory_key: str,
        title: str,
        summary: str,
        source: str,
        content: Dict[str, Any],
        case_id: Optional[int] = None,
        tags: Optional[Iterable[str]] = None,
        confidence: float = 0.0,
        success_score: float = 0.0,
    ) -> Tuple[MemoryEntry, bool]:
        entry = db.query(MemoryEntry).filter(MemoryEntry.memory_key == memory_key).first()
        created = entry is None
        if entry is None:
            entry = MemoryEntry(memory_key=memory_key, memory_type=memory_type)
            db.add(entry)

        entry.case_id = case_id
        entry.title = title
        entry.summary = summary
        entry.source = source
        entry.tags = [item for item in (tags or []) if item]
        entry.confidence = confidence
        entry.success_score = success_score
        entry.content = content
        db.flush()
        return entry, created

    def remember_episode(
        self,
        db: Session,
        *,
        case_id: int,
        memory_key: str,
        title: str,
        summary: str,
        source: str,
        content: Dict[str, Any],
        tags: Optional[Iterable[str]] = None,
        confidence: float = 0.6,
        success_score: float = 0.0,
    ) -> Tuple[MemoryEntry, bool]:
        return self.upsert_memory(
            db,
            case_id=case_id,
            memory_type=MemoryType.EPISODE,
            memory_key=memory_key,
            title=title,
            summary=summary,
            source=source,
            tags=tags,
            confidence=confidence,
            success_score=success_score,
            content=content,
        )

    def remember_pattern(
        self,
        db: Session,
        *,
        case_id: int,
        memory_key: str,
        title: str,
        summary: str,
        source: str,
        content: Dict[str, Any],
        tags: Optional[Iterable[str]] = None,
        confidence: float = 0.0,
        success_score: float = 0.0,
    ) -> Tuple[MemoryEntry, bool]:
        return self.upsert_memory(
            db,
            case_id=case_id,
            memory_type=MemoryType.PATTERN,
            memory_key=memory_key,
            title=title,
            summary=summary,
            source=source,
            tags=tags,
            confidence=confidence,
            success_score=success_score,
            content=content,
        )

    def remember_outcome(
        self,
        db: Session,
        *,
        case_id: int,
        memory_key: str,
        title: str,
        summary: str,
        source: str,
        content: Dict[str, Any],
        tags: Optional[Iterable[str]] = None,
        confidence: float = 0.0,
        success_score: float = 0.0,
    ) -> Tuple[MemoryEntry, bool]:
        return self.upsert_memory(
            db,
            case_id=case_id,
            memory_type=MemoryType.OUTCOME,
            memory_key=memory_key,
            title=title,
            summary=summary,
            source=source,
            tags=tags,
            confidence=confidence,
            success_score=success_score,
            content=content,
        )

    def remember_feedback(
        self,
        db: Session,
        *,
        memory_key: str,
        title: str,
        summary: str,
        source: str,
        content: Dict[str, Any],
        case_id: Optional[int] = None,
        tags: Optional[Iterable[str]] = None,
        confidence: float = 0.0,
        success_score: float = 0.0,
    ) -> Tuple[MemoryEntry, bool]:
        return self.upsert_memory(
            db,
            case_id=case_id,
            memory_type=MemoryType.FEEDBACK,
            memory_key=memory_key,
            title=title,
            summary=summary,
            source=source,
            tags=tags,
            confidence=confidence,
            success_score=success_score,
            content=content,
        )


memory_ingestion_service = MemoryIngestionService()
