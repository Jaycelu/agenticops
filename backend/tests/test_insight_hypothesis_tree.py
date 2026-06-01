"""Phase 4.A — InsightAnalysisAgent._parse_hypothesis_tree 纯函数单测。

不实例化 LLM client（用 __new__ 跳过 __init__）。
"""
from __future__ import annotations

from agents.insight_analysis_agent import InsightAnalysisAgent


def _agent() -> InsightAnalysisAgent:
    """Skip __init__ so we don't try to build an LLM client in the test env."""
    return InsightAnalysisAgent.__new__(InsightAnalysisAgent)


# ---------------------------------------------------------------------------
# Normal path
# ---------------------------------------------------------------------------


def test_parse_tree_sorts_by_confidence_descending():
    llm = {
        "hypotheses": [
            {"id": "h1", "cause": "low", "confidence": 0.3, "supporting_evidence_ids": []},
            {"id": "h2", "cause": "high", "confidence": 0.9, "supporting_evidence_ids": []},
            {"id": "h3", "cause": "mid", "confidence": 0.6, "supporting_evidence_ids": []},
        ]
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    assert [h["cause"] for h in out] == ["high", "mid", "low"]


def test_parse_tree_filters_invalid_evidence_ids():
    llm = {
        "hypotheses": [
            {
                "id": "h1",
                "cause": "x",
                "confidence": 0.7,
                "supporting_evidence_ids": [1, 999, "junk", 2, 1],  # 999/junk invalid; 1 dup
                "contradicting_evidence_ids": [3, 4, -1],
            }
        ]
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids={1, 2, 3, 4})
    assert out[0]["supporting_evidence_ids"] == [1, 2]  # dedup + only valid
    assert out[0]["contradicting_evidence_ids"] == [3, 4]


def test_parse_tree_clamps_confidence_to_unit_interval():
    llm = {
        "hypotheses": [
            {"id": "h1", "cause": "a", "confidence": 1.5},
            {"id": "h2", "cause": "b", "confidence": -0.2},
        ]
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    causes = {h["cause"]: h["confidence"] for h in out}
    assert causes["a"] == 1.0
    assert causes["b"] == 0.0


def test_parse_tree_assigns_default_id_when_missing():
    llm = {
        "hypotheses": [
            {"cause": "a", "confidence": 0.4},
            {"cause": "b", "confidence": 0.6},
        ]
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    # sorted desc, b first
    assert out[0]["cause"] == "b"
    # Both got auto-generated ids
    assert all(h["id"].startswith("h") for h in out)


def test_parse_tree_drops_non_dict_and_empty_cause():
    llm = {
        "hypotheses": [
            "not-a-dict",
            {"id": "h1", "cause": "", "confidence": 0.9},      # empty cause -> dropped
            {"id": "h2", "cause": "   ", "confidence": 0.9},  # whitespace-only -> dropped
            {"id": "h3", "cause": "real", "confidence": 0.5},
            None,
        ]
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    assert len(out) == 1
    assert out[0]["cause"] == "real"


# ---------------------------------------------------------------------------
# Fallback path
# ---------------------------------------------------------------------------


def test_parse_tree_fallback_synthesizes_from_legacy_fields():
    """LLM 没给 hypotheses 时，从 root_cause + confidence + cited_evidence_ids 合成单条。"""
    llm = {
        "root_cause": "optical_module_degraded",
        "confidence": 0.72,
        "cited_evidence_ids": [1, 2, 99],
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids={1, 2, 3})
    assert len(out) == 1
    h = out[0]
    assert h["cause"] == "optical_module_degraded"
    assert h["confidence"] == 0.72
    assert h["supporting_evidence_ids"] == [1, 2]  # 99 filtered
    assert h["contradicting_evidence_ids"] == []
    assert h["next_probe"] is None


def test_parse_tree_fallback_when_hypotheses_is_empty_list():
    llm = {"hypotheses": [], "root_cause": "x", "confidence": 0.4}
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    assert len(out) == 1
    assert out[0]["cause"] == "x"


def test_parse_tree_fallback_when_hypotheses_is_not_a_list():
    llm = {"hypotheses": "garbage", "root_cause": "fallback", "confidence": 0.3}
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    assert len(out) == 1
    assert out[0]["cause"] == "fallback"


def test_parse_tree_fallback_defaults_to_unknown_root_cause():
    llm = {}
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    assert len(out) == 1
    assert out[0]["cause"] == "unknown"
    assert 0.0 <= out[0]["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# next_probe handling
# ---------------------------------------------------------------------------


def test_parse_tree_preserves_next_probe_string():
    llm = {
        "hypotheses": [
            {"id": "h1", "cause": "x", "confidence": 0.5, "next_probe": "collect transceiver DOM"},
        ]
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    assert out[0]["next_probe"] == "collect transceiver DOM"


def test_parse_tree_coerces_non_string_next_probe():
    llm = {
        "hypotheses": [
            {"id": "h1", "cause": "x", "confidence": 0.5, "next_probe": 123},
        ]
    }
    out = _agent()._parse_hypothesis_tree(llm, valid_evidence_ids=set())
    assert out[0]["next_probe"] == "123"
