from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from config.settings import settings
from models.ingestion import IngestionCheckpoint
from models.log_scope import LogScope


class CheckpointLeaseUnavailable(RuntimeError):
    pass


class CheckpointService:
    def claim(self, db: Session, scope: LogScope, owner: str) -> IngestionCheckpoint:
        now = datetime.now(timezone.utc)
        checkpoint = (
            db.query(IngestionCheckpoint)
            .filter(IngestionCheckpoint.scope_id == scope.id)
            .with_for_update()
            .first()
        )
        if checkpoint is None:
            checkpoint = IngestionCheckpoint(scope_id=scope.id, total_documents=0, last_page_count=0)
            db.add(checkpoint)
            db.flush()
        if checkpoint.lease_expires_at and checkpoint.lease_expires_at > now and checkpoint.lease_owner != owner:
            raise CheckpointLeaseUnavailable("scope lease is held by another worker")
        checkpoint.lease_owner = owner
        checkpoint.lease_expires_at = now + timedelta(seconds=settings.elk_checkpoint_lease_seconds)
        db.flush()
        return checkpoint

    @staticmethod
    def advance(
        checkpoint: IngestionCheckpoint,
        *,
        timestamp: datetime,
        document_id: str,
        page_count: int,
        inserted_count: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        checkpoint.cursor_timestamp = timestamp
        checkpoint.cursor_document_id = document_id
        checkpoint.last_page_count = page_count
        checkpoint.total_documents = int(checkpoint.total_documents or 0) + inserted_count
        checkpoint.last_success_at = now
        checkpoint.lag_seconds = max(0, int((now - timestamp).total_seconds()))
        checkpoint.last_error_code = None

    @staticmethod
    def release(checkpoint: IngestionCheckpoint) -> None:
        checkpoint.lease_owner = None
        checkpoint.lease_expires_at = None


checkpoint_service = CheckpointService()
