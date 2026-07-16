from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.agent_graph import CaseTimelineEvent
from observability.metrics import metrics_registry


class CaseTimelineService:
    def append(
        self,
        db: Session,
        *,
        case_id: int,
        event_type: str,
        title: str,
        actor_type: str,
        idempotency_key: str,
        graph_run_id: str | None = None,
        task_id: int | None = None,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> CaseTimelineEvent:
        existing = db.query(CaseTimelineEvent).filter(CaseTimelineEvent.idempotency_key == idempotency_key).first()
        if existing is not None:
            return existing
        event = CaseTimelineEvent(
            case_id=case_id,
            graph_run_id=graph_run_id,
            task_id=task_id,
            event_type=event_type,
            title=title,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            payload=payload or {},
        )
        db.add(event)
        db.flush()
        metrics_registry.increment("case_timeline_event_total", event_type=event_type)
        return event


case_timeline_service = CaseTimelineService()
