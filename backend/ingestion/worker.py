from __future__ import annotations

import os
import socket
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from database import SessionLocal
from engines.case_orchestrator import case_orchestrator
from ingestion.aggregation import RULE_VERSION, log_aggregation_service
from ingestion.checkpoints import CheckpointLeaseUnavailable, checkpoint_service
from ingestion.elk_reader import elk_reader
from models.agenticops import CaseRecord
from models.ingestion import IngestionCheckpoint, LogAggregationBucket, NoiseReductionSnapshot
from models.log_scope import LogScope
from config.settings import settings


class IngestionWorker:
    def __init__(self) -> None:
        self.owner = f"{socket.gethostname()}:{os.getpid()}"

    async def run_once(self) -> bool:
        db = SessionLocal()
        scope_id: int | None = None
        try:
            scopes = (
                db.query(LogScope)
                .outerjoin(IngestionCheckpoint, IngestionCheckpoint.scope_id == LogScope.id)
                .filter(LogScope.enabled.is_(True))
                .order_by(IngestionCheckpoint.last_success_at.asc().nullsfirst(), LogScope.sort_order, LogScope.id)
                .all()
            )
            for scope in scopes:
                try:
                    checkpoint = checkpoint_service.claim(db, scope, self.owner)
                    scope_id = int(scope.id)
                    db.commit()
                    break
                except CheckpointLeaseUnavailable:
                    db.rollback()
            if scope_id is None:
                return await self.emit_pending()
        finally:
            db.close()

        db = SessionLocal()
        try:
            scope = db.query(LogScope).filter(LogScope.id == scope_id).one()
            checkpoint = db.query(IngestionCheckpoint).filter(IngestionCheckpoint.scope_id == scope_id).one()
            base_cursor = (checkpoint.cursor_timestamp, checkpoint.cursor_document_id)
            db.expunge(scope)
            db.expunge(checkpoint)
        finally:
            db.close()
        try:
            page = await elk_reader.read_page(
                scope, checkpoint, page_size=settings.elk_ingestion_page_size
            )
        except Exception as exc:
            db = SessionLocal()
            checkpoint = db.query(IngestionCheckpoint).filter(IngestionCheckpoint.scope_id == scope_id).with_for_update().first()
            if checkpoint:
                checkpoint.last_error_code = type(exc).__name__[:120]
                checkpoint_service.release(checkpoint)
                db.commit()
            db.close()
            return False

        db = SessionLocal()
        try:
            checkpoint = checkpoint_service.claim(db, db.query(LogScope).filter(LogScope.id == scope_id).one(), self.owner)
            if (checkpoint.cursor_timestamp, checkpoint.cursor_document_id) != base_cursor:
                checkpoint_service.release(checkpoint)
                db.commit()
                return False
            inserted, bucket_ids, emit_ids = log_aggregation_service.ingest_documents(db, scope_id, page.documents)
            if page.documents:
                last = page.documents[-1]
                checkpoint_service.advance(
                    checkpoint,
                    timestamp=last.timestamp,
                    document_id=last.document_id,
                    page_count=len(page.documents),
                    inserted_count=inserted,
                )
            else:
                checkpoint.last_success_at = datetime.now(timezone.utc)
                checkpoint.last_page_count = 0
            checkpoint_service.release(checkpoint)
            db.add(
                NoiseReductionSnapshot(
                    scope_id=scope_id,
                    rule_version=RULE_VERSION,
                    window_start=page.documents[0].timestamp if page.documents else datetime.now(timezone.utc),
                    window_end=page.documents[-1].timestamp if page.documents else datetime.now(timezone.utc),
                    input_count=inserted,
                    bucket_count=len(bucket_ids),
                    emitted_count=len(emit_ids),
                    suppressed_count=max(0, inserted - len(emit_ids)),
                    critical_suppressed_count=0,
                    metrics={
                        "page_count": len(page.documents),
                        "has_more": page.has_more,
                        "duplicate_reduction_rate": 0 if inserted == 0 else round(1 - (len(bucket_ids) / inserted), 6),
                        "case_compression_rate": 0 if inserted == 0 else round(1 - (len(emit_ids) / inserted), 6),
                    },
                )
            )
            db.commit()
        finally:
            db.close()
        await self.emit_pending()
        return bool(page.documents)

    _SEVERITY_RANK = {"critical": 5, "major": 4, "minor": 3, "warning": 2, "info": 1}

    async def _maybe_auto_trigger(self, db: Session, case: CaseRecord) -> None:
        if not settings.agent_auto_trigger_enabled:
            return
        threshold = self._SEVERITY_RANK.get(settings.agent_auto_trigger_min_severity.lower(), 4)
        if self._SEVERITY_RANK.get(str(case.severity or "").lower(), 0) < threshold:
            return
        whitelist = [item.strip() for item in settings.agent_auto_trigger_sites.split(",") if item.strip()]
        if whitelist and str(case.site_id) not in whitelist:
            return
        try:
            await case_orchestrator.run_case_pipeline(
                db,
                case_id=case.id,
                log_query=case.device_ip or case.host,
            )
            logger.bind(case_id=case.id).info("agent_graph_auto_triggered")
        except Exception:
            logger.bind(case_id=case.id).warning("agent_graph_auto_trigger_failed")

    async def emit_pending(self) -> bool:
        db = SessionLocal()
        try:
            bucket = (
                db.query(LogAggregationBucket)
                .filter(LogAggregationBucket.decision == "emit", LogAggregationBucket.emitted_at.is_(None))
                .order_by(LogAggregationBucket.window_start, LogAggregationBucket.id)
                .with_for_update(skip_locked=True)
                .first()
            )
            if bucket is None:
                db.rollback()
                return False
            case = await case_orchestrator.intake_case(
                db,
                title=f"聚合日志事件：{bucket.device_key}",
                source_type="log_aggregate",
                source_system="ELK",
                dedup_key=f"elk-aggregate:{bucket.id}",
                severity=bucket.severity,
                device_ip=bucket.device_key if bucket.device_key.count(".") == 3 else None,
                host=bucket.device_key,
                summary=f"{bucket.event_count} 条相同日志聚合为一个事件",
                occurred_at=bucket.window_start,
                raw_payload={
                    "aggregation_bucket_id": int(bucket.id),
                    "signature": bucket.signature,
                    "event_count": bucket.event_count,
                    "evidence_document_ids": bucket.sample_document_ids,
                    "rule_version": bucket.rule_version,
                    "decision_reason": bucket.decision_reason,
                },
                normalized_payload={"signature": bucket.signature, "event_count": bucket.event_count},
            )
            bucket = db.query(LogAggregationBucket).filter(LogAggregationBucket.id == bucket.id).one()
            bucket.emitted_case_id = case.id
            bucket.emitted_at = datetime.now(timezone.utc)
            db.commit()
            await self._maybe_auto_trigger(db, case)
            return True
        finally:
            db.close()


ingestion_worker = IngestionWorker()
