"""Phase 5 — embedding_service + MemoryRetriever 单元测试。

retrieve() 部分用 sqlite 内存库种 MemoryEntry；不依赖真实 LLM / pgvector。
"""
from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import automation  # noqa: F401 - registers FK target tables
from models.agenticops import MemoryEntry, MemoryType
from services.embedding_service import NullEmbedder, build_embedder, cosine_similarity
from services.memory_retriever import MemoryRetriever, memory_retriever, tokenize


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


def test_cosine_identical_vectors():
    assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == 1.0


def test_cosine_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_empty_or_dimension_mismatch():
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity(None, [1.0]) == 0.0
    assert cosine_similarity([1.0], None) == 0.0


def test_cosine_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_known_value():
    # [1,1] vs [1,0] -> cos = 1/sqrt(2)
    assert abs(cosine_similarity([1.0, 1.0], [1.0, 0.0]) - 1.0 / math.sqrt(2)) < 1e-9


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------


def test_null_embedder_returns_none():
    emb = NullEmbedder()
    assert emb.is_enabled is False
    assert asyncio.run(emb.embed("anything")) is None


def test_build_embedder_defaults_to_null(monkeypatch):
    from services import embedding_service as es

    monkeypatch.setattr(es.settings, "llm_embedding_model", "", raising=False)
    assert isinstance(build_embedder(), NullEmbedder)


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------


def test_tokenize_basic():
    toks = tokenize("Core Switch CRC error")
    assert {"core", "switch", "crc", "error"}.issubset(toks)


def test_tokenize_drops_single_chars_and_empty():
    assert tokenize("a bb ccc") == {"bb", "ccc"}
    assert tokenize("") == set()
    assert tokenize(None) == set()


# ---------------------------------------------------------------------------
# MemoryRetriever — fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _mem(
    db,
    *,
    mem_id,
    memory_type,
    key,
    title,
    summary="",
    tags=None,
    confidence=0.5,
    success=0.0,
    content=None,
    embedding=None,
    case_id=None,
    created_at=None,
):
    entry = MemoryEntry(
        id=mem_id,
        memory_type=memory_type,
        memory_key=key,
        title=title,
        summary=summary,
        source="test",
        tags=tags or [],
        confidence=confidence,
        success_score=success,
        content=content or {},
        embedding=embedding,
        case_id=case_id,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    return entry


# ---------------------------------------------------------------------------
# MemoryRetriever — lexical / metadata
# ---------------------------------------------------------------------------


def test_retrieve_lexical_overlap_ranks_higher(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="core switch CRC error")
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="unrelated power supply")
    db_session.commit()
    out = memory_retriever.retrieve(db_session, query_text="core switch CRC", limit=5)
    assert out[0].id == 1


def test_retrieve_without_embeddings_still_works(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="core switch fault")
    db_session.commit()
    out = memory_retriever.retrieve(db_session, query_text="core switch", limit=5)
    assert len(out) == 1
    assert out[0].components["cosine"] == 0.0


def test_retrieve_excludes_given_case(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="alpha signal", case_id=77)
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="alpha signal", case_id=88)
    db_session.commit()
    out = memory_retriever.retrieve(db_session, query_text="alpha signal", exclude_case_id=77, limit=5)
    ids = {s.id for s in out}
    assert 1 not in ids and 2 in ids


def test_retrieve_site_match_scores_higher(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="alpha", content={"site_id": 5})
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="alpha", content={"site_id": 9})
    db_session.commit()
    out = memory_retriever.retrieve(db_session, query_text="alpha", site_id=5, limit=5)
    assert out[0].id == 1


def test_retrieve_recency_favors_newer(db_session):
    old = datetime.now(timezone.utc) - timedelta(days=90)
    new = datetime.now(timezone.utc)
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="beta event", created_at=old)
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="beta event", created_at=new)
    db_session.commit()
    out = memory_retriever.retrieve(db_session, query_text="beta event", limit=5)
    assert out[0].id == 2


def test_retrieve_tag_overlap_scores(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="gamma", tags=["10.0.0.1", "crc"])
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="gamma", tags=["other"])
    db_session.commit()
    out = memory_retriever.retrieve(db_session, query_text="gamma", tags=["10.0.0.1"], limit=5)
    assert out[0].id == 1


def test_retrieve_respects_limit(db_session):
    for i in range(10):
        _mem(db_session, mem_id=i + 1, memory_type=MemoryType.PATTERN, key=f"k{i}", title="delta record")
    db_session.commit()
    out = memory_retriever.retrieve(db_session, query_text="delta record", limit=3)
    assert len(out) == 3


# ---------------------------------------------------------------------------
# MemoryRetriever — semantic cosine
# ---------------------------------------------------------------------------


def test_retrieve_cosine_breaks_lexical_tie(db_session):
    # Both titles lexically identical; the entry whose embedding is closer wins.
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="signal anomaly", embedding=[1.0, 0.0])
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="signal anomaly", embedding=[0.0, 1.0])
    db_session.commit()
    out = memory_retriever.retrieve(
        db_session, query_text="signal anomaly", query_embedding=[0.96, 0.04], limit=5
    )
    assert out[0].id == 1
    assert out[0].components["cosine"] > out[1].components["cosine"]


# ---------------------------------------------------------------------------
# MemoryRetriever — task profiles
# ---------------------------------------------------------------------------


def test_rca_profile_prefers_pattern_memory(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="core switch fault")
    _mem(db_session, mem_id=2, memory_type=MemoryType.EPISODE, key="k2", title="core switch fault")
    db_session.commit()
    out = memory_retriever.retrieve(db_session, task_type="rca", query_text="core switch fault", limit=5)
    assert out[0].id == 1


def test_remediation_profile_prefers_outcome_with_success(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.OUTCOME, key="k1", title="fix interface", success=0.9)
    _mem(db_session, mem_id=2, memory_type=MemoryType.EPISODE, key="k2", title="fix interface", success=0.0)
    db_session.commit()
    out = memory_retriever.retrieve(db_session, task_type="remediation", query_text="fix interface", limit=5)
    assert out[0].id == 1


def test_unknown_task_type_falls_back_to_default(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="epsilon")
    db_session.commit()
    out = memory_retriever.retrieve(db_session, task_type="does-not-exist", query_text="epsilon", limit=5)
    assert len(out) == 1


# ---------------------------------------------------------------------------
# case_memory_hits — drop-in shape
# ---------------------------------------------------------------------------


def test_case_memory_hits_returns_legacy_shape(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="core switch CRC", summary="s")
    db_session.commit()
    case = SimpleNamespace(
        id=500, title="core switch CRC error", summary="", device_ip="10.0.0.1", host="sw1", site_id=1
    )
    hits = MemoryRetriever().case_memory_hits(db_session, case=case, runtime={}, signal_family="crc")
    assert len(hits) == 1
    expected_keys = {
        "id", "memory_type", "title", "summary", "confidence",
        "success_score", "content", "case_id", "retrieval_score", "retrieval_components",
    }
    assert expected_keys.issubset(hits[0].keys())


def test_case_memory_hits_excludes_self_case(db_session):
    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="core switch CRC", case_id=500)
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="core switch CRC", case_id=600)
    db_session.commit()
    case = SimpleNamespace(id=500, title="core switch CRC", summary="", device_ip=None, host=None, site_id=None)
    hits = MemoryRetriever().case_memory_hits(db_session, case=case, runtime={})
    assert all(h["id"] != 1 for h in hits)


# ---------------------------------------------------------------------------
# Phase 5 (建议5) — backfill_memory_embeddings
# ---------------------------------------------------------------------------


def test_backfill_skipped_when_embedder_disabled(db_session, monkeypatch):
    from services import embedding_service as es

    monkeypatch.setattr(es.settings, "llm_embedding_model", "", raising=False)
    result = asyncio.run(es.backfill_memory_embeddings(db_session, limit=10))
    assert result["status"] == "skipped"
    assert result["reason"] == "embedder_disabled"


def test_backfill_embeds_only_pending_entries(db_session, monkeypatch):
    from services import embedding_service as es

    _mem(db_session, mem_id=1, memory_type=MemoryType.PATTERN, key="k1", title="core fault", summary="crc")
    _mem(db_session, mem_id=2, memory_type=MemoryType.PATTERN, key="k2", title="agg flap", embedding=[0.1, 0.2])
    db_session.commit()

    class _FakeEmbedder:
        is_enabled = True

        async def embed(self, text):
            return [0.5, 0.5]

    monkeypatch.setattr(es, "build_embedder", lambda: _FakeEmbedder())
    result = asyncio.run(es.backfill_memory_embeddings(db_session, limit=10))

    assert result["status"] == "ok"
    assert result["embedded"] == 1  # only mem 1 had a NULL embedding
    entry1 = db_session.query(MemoryEntry).filter(MemoryEntry.id == 1).one()
    assert entry1.embedding == [0.5, 0.5]
    entry2 = db_session.query(MemoryEntry).filter(MemoryEntry.id == 2).one()
    assert entry2.embedding == [0.1, 0.2]  # untouched
