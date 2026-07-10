from __future__ import annotations

import pytest

from harness.contracts import EvidenceBundle, EvidenceQuerySpec


pytestmark = pytest.mark.unit


def test_evidence_bundle_round_trip_preserves_traceability() -> None:
    bundle = EvidenceBundle(
        case_id=42,
        case_code="CASE-42",
        queries=EvidenceQuerySpec(
            elk_query="host:edge-01",
            elk_time_range="-15m,now",
            elk_limit=200,
            netbox_device_id=1001,
            zabbix_host="edge-01",
        ),
        evidence_item_ids=[10, 11],
        runtime_keys=["device"],
        notes=["baseline"],
    )

    payload = bundle.to_dict()

    assert payload["case_id"] == 42
    assert payload["queries"]["netbox_device_id"] == 1001
    assert payload["evidence_item_ids"] == [10, 11]
    assert payload["runtime_keys"] == ["device"]
