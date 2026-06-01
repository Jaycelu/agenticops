"""Phase 4.B — TopologyCorrelationService 单元测试。

拓扑：core-01(1) — agg-01(2) — acc-01(3) — ap-01(4)，全部在 SITE-A。
另有 other-core(5) 在 SITE-B。

用 sqlite 内存库 + 注入的 fake topology fetcher。
"""
from __future__ import annotations

import asyncio
import itertools
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import Base
from models import automation  # noqa: F401 - registers AssetDevice + FK target tables
from models.agenticops import (
    CaseRecord,
    CaseStatus,
    EvidenceItem,
    EvidenceType,
    SourceEvent,
    SourceEventStatus,
)
from models.automation import AssetDevice
from services.topology_correlation_service import TopologyCorrelationService


# ---------------------------------------------------------------------------
# Fake topology graph
# ---------------------------------------------------------------------------

_TOPO = {
    1: {"success": True, "data": {"links": [{"peer_device": "agg-01"}]}},
    2: {"success": True, "data": {"links": [{"peer_device": "core-01"}, {"peer_device": "acc-01"}]}},
    3: {"success": True, "data": {"links": [{"peer_device": "agg-01"}, {"peer_device": "ap-01"}]}},
    4: {"success": True, "data": {"links": [{"peer_device": "acc-01"}]}},
}


async def fake_fetcher(device_id):
    return _TOPO.get(device_id, {"success": False})


async def failing_fetcher(device_id):
    raise RuntimeError("netbox unreachable")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    counter = itertools.count(7001)

    def assign_evidence_id(mapper, connection, target):
        if target.id is None:
            target.id = next(counter)

    event.listen(EvidenceItem, "before_insert", assign_evidence_id)
    try:
        yield db
    finally:
        event.remove(EvidenceItem, "before_insert", assign_evidence_id)
        db.close()


def _seed_devices(db):
    rows = [
        (1, "core-01", "Core Switch", "SITE-A"),
        (2, "agg-01", "Aggregation Switch", "SITE-A"),
        (3, "acc-01", "Access Switch", "SITE-A"),
        (4, "ap-01", "Wireless AP", "SITE-A"),
        (5, "other-core", "Core Switch", "SITE-B"),
    ]
    for nid, name, role, site in rows:
        db.add(AssetDevice(netbox_device_id=nid, name=name, role=role, site=site))
    db.commit()


def _open_case(db, *, case_id, code, netbox_device_id, site_id,
               status=CaseStatus.INVESTIGATING, opened_minutes_ago=5):
    case = CaseRecord(
        id=case_id,
        case_code=code,
        title=f"case {code}",
        netbox_device_id=netbox_device_id,
        site_id=site_id,
        status=status,
        opened_at=datetime.now(timezone.utc) - timedelta(minutes=opened_minutes_ago),
    )
    db.add(case)
    db.commit()
    return case


def _svc():
    return TopologyCorrelationService(topology_fetcher=fake_fetcher)


# ---------------------------------------------------------------------------
# role_tier
# ---------------------------------------------------------------------------


def test_role_tier_classification():
    svc = TopologyCorrelationService()
    assert svc.role_tier("Core Switch") == 0
    assert svc.role_tier("核心交换机") == 0
    assert svc.role_tier("Aggregation Switch") == 1
    assert svc.role_tier("汇聚交换机") == 1
    assert svc.role_tier("Access Switch") == 2
    assert svc.role_tier("Wireless AP") == 3
    assert svc.role_tier("服务器") == 3
    assert svc.role_tier(None) == 2          # default tier
    assert svc.role_tier("mystery-role") == 2


# ---------------------------------------------------------------------------
# collect_upstream
# ---------------------------------------------------------------------------


def test_collect_upstream_from_access_switch(db_session):
    _seed_devices(db_session)
    upstream = asyncio.run(_svc().collect_upstream(db_session, netbox_device_id=3, max_hops=2))
    assert upstream == {"agg-01": 1, "core-01": 2}


def test_collect_upstream_respects_max_hops(db_session):
    _seed_devices(db_session)
    upstream = asyncio.run(_svc().collect_upstream(db_session, netbox_device_id=3, max_hops=1))
    assert upstream == {"agg-01": 1}  # core-01 is 2 hops away — excluded


def test_collect_upstream_never_descends_downstream(db_session):
    _seed_devices(db_session)
    upstream = asyncio.run(_svc().collect_upstream(db_session, netbox_device_id=3, max_hops=3))
    assert "ap-01" not in upstream  # ap-01 is downstream of acc-01


def test_collect_upstream_from_core_is_empty(db_session):
    _seed_devices(db_session)
    upstream = asyncio.run(_svc().collect_upstream(db_session, netbox_device_id=1, max_hops=3))
    assert upstream == {}  # core has nothing upstream of it


def test_collect_upstream_fetcher_failure_degrades_gracefully(db_session):
    _seed_devices(db_session)
    svc = TopologyCorrelationService(topology_fetcher=failing_fetcher)
    upstream = asyncio.run(svc.collect_upstream(db_session, netbox_device_id=3, max_hops=2))
    assert upstream == {}  # fail-open: no upstream discovered, never raises


# ---------------------------------------------------------------------------
# find_parent_case
# ---------------------------------------------------------------------------


def test_find_parent_case_1hop_hit(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5001, code="CASE-AGG", netbox_device_id=2, site_id=100)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is not None
    assert hit.parent_case_code == "CASE-AGG"
    assert hit.hops == 1
    assert hit.confidence == 0.85


def test_find_parent_case_2hop_hit(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5002, code="CASE-CORE", netbox_device_id=1, site_id=100)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is not None
    assert hit.parent_case_code == "CASE-CORE"
    assert hit.hops == 2
    assert hit.confidence == 0.68


def test_find_parent_case_prefers_closest_anchor(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5003, code="CASE-CORE", netbox_device_id=1, site_id=100)
    _open_case(db_session, case_id=5004, code="CASE-AGG", netbox_device_id=2, site_id=100)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit.parent_case_code == "CASE-AGG"  # 1 hop beats 2 hops
    assert hit.hops == 1


def test_find_parent_case_downstream_anchor_no_hit(db_session):
    """An open case on a device DOWNSTREAM of the candidate must not be a parent."""
    _seed_devices(db_session)
    _open_case(db_session, case_id=5005, code="CASE-AP", netbox_device_id=4, site_id=100)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is None


def test_find_parent_case_other_site_no_hit(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5006, code="CASE-AGG", netbox_device_id=2, site_id=200)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is None


def test_find_parent_case_resolved_case_no_hit(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5007, code="CASE-AGG", netbox_device_id=2,
               site_id=100, status=CaseStatus.RESOLVED)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is None


def test_find_parent_case_stale_case_outside_window_no_hit(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5008, code="CASE-AGG", netbox_device_id=2,
               site_id=100, opened_minutes_ago=120)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is None


def test_find_parent_case_no_device_id_returns_none(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5009, code="CASE-AGG", netbox_device_id=2, site_id=100)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=None))
    assert hit is None


def test_find_parent_case_same_device_excluded(db_session):
    """An open case on the SAME device as the candidate must not self-correlate."""
    _seed_devices(db_session)
    _open_case(db_session, case_id=5010, code="CASE-SELF", netbox_device_id=3, site_id=100)
    hit = asyncio.run(_svc().find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is None


# ---------------------------------------------------------------------------
# attach_derivative_evidence
# ---------------------------------------------------------------------------


def test_attach_derivative_evidence_creates_evidence_and_marks_source_event(db_session):
    _seed_devices(db_session)
    _open_case(db_session, case_id=5011, code="CASE-AGG", netbox_device_id=2, site_id=100)
    source_event = SourceEvent(
        id=9100,
        source_type="log_signal",
        source_system="ELK_SAMPLER",
        dedup_key="log-sample:777",
        title="acc-01 日志信号",
        severity="warning",
        status=SourceEventStatus.NEW,
    )
    db_session.add(source_event)
    db_session.commit()

    svc = _svc()
    hit = asyncio.run(svc.find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is not None

    evidence = svc.attach_derivative_evidence(
        db_session,
        hit,
        derivative_dedup_key="log-sample:777",
        candidate_summary="test derivative",
        candidate_payload={"sample_id": 777},
    )
    db_session.commit()

    assert evidence.case_id == 5011
    assert evidence.evidence_type == EvidenceType.EXTERNAL_CONTEXT
    assert evidence.source_system == "topology_correlation"
    assert evidence.source_event_id == 9100
    assert evidence.payload["correlation"]["parent_case_code"] == "CASE-AGG"

    db_session.refresh(source_event)
    assert source_event.status == SourceEventStatus.CORRELATED


def test_attach_derivative_evidence_without_source_event(db_session):
    """When no derivative SourceEvent matches the dedup_key, evidence is still created."""
    _seed_devices(db_session)
    _open_case(db_session, case_id=5012, code="CASE-AGG", netbox_device_id=2, site_id=100)
    svc = _svc()
    hit = asyncio.run(svc.find_parent_case(db_session, site_id=100, netbox_device_id=3))
    assert hit is not None
    evidence = svc.attach_derivative_evidence(db_session, hit, derivative_dedup_key="nonexistent")
    db_session.commit()
    assert evidence.case_id == 5012
    assert evidence.source_event_id is None
