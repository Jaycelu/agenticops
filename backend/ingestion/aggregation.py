from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from ingestion.schemas import ELKDocument
from models.ingestion import IngestedLogEvent, LogAggregationBucket
from probes.redaction import redact_output


RULE_VERSION = "2026.07.1"
WINDOW_MINUTES = 5
_VARIABLES = re.compile(r"\b(?:[0-9a-f]{8,}|\d+|(?:\d{1,3}\.){3}\d{1,3})\b", re.I)


def normalize_signature(message: str) -> tuple[str, str]:
    redacted = redact_output(message, max_bytes=8192)[0]
    normalized = " ".join(_VARIABLES.sub("<var>", redacted.lower()).split())[:1000]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest(), normalized


def window_start(value: datetime) -> datetime:
    utc = value.astimezone(timezone.utc)
    minute = utc.minute - (utc.minute % WINDOW_MINUTES)
    return utc.replace(minute=minute, second=0, microsecond=0)


def emission_threshold(severity: str) -> int:
    value = severity.lower()
    if value in {"emergency", "emergencies", "alert", "critical", "error", "high"}:
        return 1
    if value in {"warning", "warn", "medium"}:
        return 3
    return 10


class LogAggregationService:
    def ingest_documents(
        self, db: Session, scope_id: int, documents: Iterable[ELKDocument]
    ) -> tuple[int, list[int], list[int]]:
        inserted = 0
        emit_bucket_ids: list[int] = []
        touched_bucket_ids: list[int] = []
        for document in documents:
            exists = db.query(IngestedLogEvent.id).filter(
                IngestedLogEvent.scope_id == scope_id,
                IngestedLogEvent.external_document_id == document.document_id,
            ).first()
            if exists:
                continue
            signature, normalized = normalize_signature(document.message)
            start = window_start(document.timestamp)
            bucket = db.query(LogAggregationBucket).filter(
                LogAggregationBucket.scope_id == scope_id,
                LogAggregationBucket.window_start == start,
                LogAggregationBucket.device_key == document.device_key,
                LogAggregationBucket.signature == signature,
            ).first()
            if bucket is None:
                bucket = LogAggregationBucket(
                    scope_id=scope_id,
                    window_start=start,
                    window_end=start + timedelta(minutes=WINDOW_MINUTES),
                    device_key=document.device_key,
                    signature=signature,
                    severity=document.severity,
                    event_count=0,
                    sample_document_ids=[],
                    rule_version=RULE_VERSION,
                    decision="suppress",
                    decision_reason="below emission threshold",
                )
                db.add(bucket)
                db.flush()
            bucket.event_count += 1
            touched_bucket_ids.append(int(bucket.id))
            samples = list(bucket.sample_document_ids or [])
            if len(samples) < 20:
                samples.append(document.document_id)
                bucket.sample_document_ids = samples
            threshold = emission_threshold(bucket.severity)
            if bucket.event_count >= threshold:
                bucket.decision = "emit"
                bucket.decision_reason = f"count reached threshold {threshold}"
                if bucket.emitted_at is None:
                    emit_bucket_ids.append(int(bucket.id))
            event = IngestedLogEvent(
                scope_id=scope_id,
                external_document_id=document.document_id,
                occurred_at=document.timestamp,
                device_key=document.device_key,
                severity=document.severity,
                signature=signature,
                normalized_message=normalized,
                source_metadata=document.metadata,
                decision=bucket.decision,
                aggregation_bucket_id=bucket.id,
            )
            db.add(event)
            inserted += 1
        db.flush()
        return inserted, sorted(set(touched_bucket_ids)), sorted(set(emit_bucket_ids))


log_aggregation_service = LogAggregationService()
