from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import require_permissions
from auth.rbac import Permission
from auth.schemas import Principal
from database import get_db
from models.ingestion import IngestionCheckpoint, NoiseReductionSnapshot
from models.log_scope import LogScope


router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.get("/checkpoints")
def checkpoints(
    principal: Principal = Depends(require_permissions(Permission.INTEGRATIONS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    del principal
    rows = (
        db.query(IngestionCheckpoint, LogScope)
        .join(LogScope, LogScope.id == IngestionCheckpoint.scope_id)
        .order_by(LogScope.sort_order, LogScope.id)
        .all()
    )
    return {
        "items": [
            {
                "scope_id": scope.id,
                "scope_key": scope.scope_key,
                "cursor_timestamp": checkpoint.cursor_timestamp,
                "cursor_document_id": checkpoint.cursor_document_id,
                "last_success_at": checkpoint.last_success_at,
                "last_page_count": checkpoint.last_page_count,
                "total_documents": checkpoint.total_documents,
                "lag_seconds": checkpoint.lag_seconds,
                "last_error_code": checkpoint.last_error_code,
                "lease_active": bool(
                    checkpoint.lease_expires_at and checkpoint.lease_expires_at > datetime.now(timezone.utc)
                ),
            }
            for checkpoint, scope in rows
        ]
    }


@router.get("/noise-report")
def noise_report(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    principal: Principal = Depends(require_permissions(Permission.INTEGRATIONS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    del principal
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    totals = db.query(
        func.coalesce(func.sum(NoiseReductionSnapshot.input_count), 0),
        func.coalesce(func.sum(NoiseReductionSnapshot.bucket_count), 0),
        func.coalesce(func.sum(NoiseReductionSnapshot.emitted_count), 0),
        func.coalesce(func.sum(NoiseReductionSnapshot.critical_suppressed_count), 0),
    ).filter(NoiseReductionSnapshot.created_at >= since).one()
    input_count, bucket_count, emitted_count, critical_suppressed = (int(item or 0) for item in totals)
    return {
        "window_hours": hours,
        "input_count": input_count,
        "bucket_count": bucket_count,
        "emitted_count": emitted_count,
        "duplicate_reduction_rate": 0 if input_count == 0 else round(1 - bucket_count / input_count, 6),
        "case_compression_rate": 0 if input_count == 0 else round(1 - emitted_count / input_count, 6),
        "critical_suppressed_count": critical_suppressed,
        "shadow_gate_passed": input_count > 0 and critical_suppressed == 0,
    }
