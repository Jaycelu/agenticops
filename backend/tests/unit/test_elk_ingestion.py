from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ingestion.aggregation import emission_threshold, normalize_signature, window_start
from ingestion.elk_reader import ELKReaderError, elk_reader
from ingestion.replay import evaluate_replay
from ingestion.schemas import ELKDocument
from models.ingestion import IngestionCheckpoint


pytestmark = pytest.mark.unit


def document(index: int, *, timestamp: datetime | None = None, severity: str = "warning") -> ELKDocument:
    return ELKDocument(
        document_id=f"doc-{index:05d}",
        timestamp=timestamp or datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc) + timedelta(milliseconds=index),
        message=f"Interface Gi0/{index % 2} changed state at sequence {index}",
        device_key="edge-01",
        severity=severity,
    )


def test_stable_cursor_pages_cover_more_than_one_thousand_without_gap() -> None:
    rows = [document(index) for index in range(1501)]
    checkpoint = IngestionCheckpoint(scope_id=1)
    observed: list[str] = []

    for start in range(0, len(rows), 500):
        page = rows[start : start + 500]
        elk_reader._validate_order(page, checkpoint)
        observed.extend(item.document_id for item in page)
        checkpoint.cursor_timestamp = page[-1].timestamp
        checkpoint.cursor_document_id = page[-1].document_id

    assert observed == [item.document_id for item in rows]
    assert len(set(observed)) == 1501


def test_same_timestamp_documents_are_ordered_by_unique_document_id() -> None:
    timestamp = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
    rows = [document(index, timestamp=timestamp) for index in range(5)]
    elk_reader._validate_order(rows, IngestionCheckpoint(scope_id=1))

    with pytest.raises(ELKReaderError, match="strictly sorted"):
        elk_reader._validate_order([rows[1], rows[0]], IngestionCheckpoint(scope_id=1))
    with pytest.raises(ELKReaderError, match="strictly sorted"):
        elk_reader._validate_order([rows[0], rows[0]], IngestionCheckpoint(scope_id=1))


def test_proxy_reader_refuses_rows_without_stable_document_id() -> None:
    with pytest.raises(ELKReaderError, match="stable document id"):
        elk_reader._proxy_document(
            {"timestamp": 1784109600000, "hostname": "edge-01", "raw_message": "link down"}
        )


def test_aggregation_rules_never_suppress_critical_and_normalize_variables() -> None:
    first_hash, first = normalize_signature("Interface Gi0/1 error count 17 password hidden")
    second_hash, second = normalize_signature("Interface Gi0/1 error count 99 password another")

    assert emission_threshold("critical") == 1
    assert emission_threshold("warning") == 3
    assert emission_threshold("informational") == 10
    assert first_hash == second_hash
    assert "hidden" not in first
    assert "another" not in second
    assert window_start(datetime(2026, 7, 15, 10, 7, 55, tzinfo=timezone.utc)).minute == 5


def test_shadow_replay_reports_compression_and_critical_false_suppression() -> None:
    rows = [document(index, severity="warning") for index in range(6)]
    report = evaluate_replay(rows, critical_truth_ids={rows[0].document_id})

    assert report["input_count"] == 6
    assert report["emitted_count"] >= 1
    assert report["critical_truth_suppressed"] == 0
    assert report["safe_for_shadow_promotion"] is True
