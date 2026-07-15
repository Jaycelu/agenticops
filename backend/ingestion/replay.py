from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from ingestion.aggregation import emission_threshold, normalize_signature
from ingestion.schemas import ELKDocument


def evaluate_replay(documents: Iterable[ELKDocument], critical_truth_ids: set[str] | None = None) -> dict[str, Any]:
    rows = list(documents)
    groups: dict[tuple[str, str], list[ELKDocument]] = defaultdict(list)
    for document in rows:
        signature = normalize_signature(document.message)[0]
        groups[(document.device_key, signature)].append(document)
    emitted_groups = 0
    critical_suppressed = 0
    truth = critical_truth_ids or set()
    for group in groups.values():
        threshold = emission_threshold(group[0].severity)
        emitted = len(group) >= threshold
        if emitted:
            emitted_groups += 1
        if not emitted and any(item.document_id in truth for item in group):
            critical_suppressed += 1
    input_count = len(rows)
    duplicate_reduction = 0.0 if input_count == 0 else 1 - (len(groups) / input_count)
    case_compression = 0.0 if input_count == 0 else 1 - (emitted_groups / input_count)
    return {
        "rule_version": "2026.07.1",
        "input_count": input_count,
        "bucket_count": len(groups),
        "emitted_count": emitted_groups,
        "duplicate_reduction_rate": round(duplicate_reduction, 6),
        "case_compression_rate": round(case_compression, 6),
        "critical_truth_suppressed": critical_suppressed,
        "safe_for_shadow_promotion": critical_suppressed == 0,
    }
