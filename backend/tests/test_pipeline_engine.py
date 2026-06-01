"""PipelineEngine + PlaybookRegistry 单元测试（Phase 3）。

完全在内存中跑，不依赖 DB / fastapi / 真实 agent。
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from pipelines.engine import PipelineEngine
from pipelines.registry import PlaybookRegistry
from pipelines.schemas import Playbook, PlaybookStep, PipelineState, StepKind


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**extras: Any) -> PipelineState:
    return PipelineState(
        db=None,
        case=None,
        context=SimpleNamespace(prior_claims=[], harness_trace=[]),
        extras=dict(extras),
    )


def _noop_agent_fn(state, agent):  # pragma: no cover - replaced per-test
    return None


def _write_playbook(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        json.dump(data, fp)


# ---------------------------------------------------------------------------
# Engine: sequential agent + hook
# ---------------------------------------------------------------------------


def test_engine_runs_agent_then_hook_in_order():
    calls: list = []

    async def fake_agent_fn(state, agent):
        calls.append(("agent", agent.name))

    async def hook_a(state):
        calls.append(("hook", "a"))

    playbook = Playbook(
        id="p",
        name="p",
        steps=[
            PlaybookStep(id="s1", kind=StepKind.AGENT, agent="agent_x"),
            PlaybookStep(id="s2", kind=StepKind.HOOK, hook="a"),
        ],
    )
    engine = PipelineEngine(
        agents={"agent_x": SimpleNamespace(name="agent_x")},
        hooks={"a": hook_a},
        predicates={},
        execute_agent_fn=fake_agent_fn,
    )
    state = _state()
    asyncio.run(engine.execute(state, playbook))
    assert calls == [("agent", "agent_x"), ("hook", "a")]
    # Trace records both steps.
    step_ids = [entry.get("step") for entry in state.trace if "step" in entry]
    assert step_ids == ["s1", "s2"]


# ---------------------------------------------------------------------------
# predicate = False skips
# ---------------------------------------------------------------------------


def test_engine_skips_step_when_predicate_false():
    calls: list = []

    async def hook_x(state):
        calls.append("called")

    playbook = Playbook(
        id="p",
        name="p",
        steps=[PlaybookStep(id="s1", kind=StepKind.HOOK, hook="x", predicate="never")],
    )
    engine = PipelineEngine(
        agents={},
        hooks={"x": hook_x},
        predicates={"never": lambda _s: False},
        execute_agent_fn=_noop_agent_fn,
    )
    state = _state()
    asyncio.run(engine.execute(state, playbook))
    assert calls == []
    assert any(entry.get("skipped") for entry in state.trace)


def test_engine_missing_predicate_is_treated_as_false():
    """Fail-closed: an unregistered predicate skips the step instead of running it."""
    calls: list = []

    async def hook_x(state):
        calls.append("called")

    playbook = Playbook(
        id="p",
        name="p",
        steps=[PlaybookStep(id="s1", kind=StepKind.HOOK, hook="x", predicate="missing")],
    )
    engine = PipelineEngine(
        agents={},
        hooks={"x": hook_x},
        predicates={},  # 'missing' is not registered
        execute_agent_fn=_noop_agent_fn,
    )
    state = _state()
    asyncio.run(engine.execute(state, playbook))
    assert calls == []
    assert any(entry.get("reason") == "predicate_not_registered" for entry in state.trace)


# ---------------------------------------------------------------------------
# LOOP: full iterations
# ---------------------------------------------------------------------------


def test_engine_loop_completes_all_iterations_when_no_break_predicate():
    seen: list = []

    async def body(state):
        seen.append(state.extras["loop_iter"])

    playbook = Playbook(
        id="p",
        name="p",
        steps=[
            PlaybookStep(
                id="loop1",
                kind=StepKind.LOOP,
                max_iterations=3,
                steps=[PlaybookStep(id="body", kind=StepKind.HOOK, hook="b")],
            )
        ],
    )
    engine = PipelineEngine(
        agents={},
        hooks={"b": body},
        predicates={},
        execute_agent_fn=_noop_agent_fn,
    )
    state = _state()
    asyncio.run(engine.execute(state, playbook))
    assert seen == [0, 1, 2]
    assert any(entry.get("completed_iterations") == 3 for entry in state.trace)


# ---------------------------------------------------------------------------
# LOOP: break_predicate exits early
# ---------------------------------------------------------------------------


def test_engine_loop_breaks_when_predicate_true_after_substeps():
    seen: list = []

    async def body(state):
        seen.append(state.extras["loop_iter"])

    playbook = Playbook(
        id="p",
        name="p",
        steps=[
            PlaybookStep(
                id="loop1",
                kind=StepKind.LOOP,
                max_iterations=5,
                break_predicate="brk",
                steps=[PlaybookStep(id="body", kind=StepKind.HOOK, hook="b")],
            )
        ],
    )
    engine = PipelineEngine(
        agents={},
        hooks={"b": body},
        predicates={"brk": lambda s: int(s.extras.get("loop_iter") or 0) >= 1},
        execute_agent_fn=_noop_agent_fn,
    )
    state = _state()
    asyncio.run(engine.execute(state, playbook))
    # Body runs on iter 0, then again on iter 1, then break_predicate returns True -> stop.
    assert seen == [0, 1]
    assert any(entry.get("broke_at") == 1 for entry in state.trace)


# ---------------------------------------------------------------------------
# LOOP substep with its own predicate
# ---------------------------------------------------------------------------


def test_engine_loop_substep_predicate_gates_only_that_substep():
    main_seen: list = []
    extra_seen: list = []

    async def main(state):
        main_seen.append(state.extras["loop_iter"])

    async def extra(state):
        extra_seen.append(state.extras["loop_iter"])

    playbook = Playbook(
        id="p",
        name="p",
        steps=[
            PlaybookStep(
                id="loop1",
                kind=StepKind.LOOP,
                max_iterations=3,
                steps=[
                    PlaybookStep(id="m", kind=StepKind.HOOK, hook="m"),
                    PlaybookStep(id="e", kind=StepKind.HOOK, hook="e", predicate="first_only"),
                ],
            )
        ],
    )
    engine = PipelineEngine(
        agents={},
        hooks={"m": main, "e": extra},
        predicates={"first_only": lambda s: int(s.extras.get("loop_iter") or 0) == 0},
        execute_agent_fn=_noop_agent_fn,
    )
    asyncio.run(engine.execute(_state(), playbook))
    assert main_seen == [0, 1, 2]
    assert extra_seen == [0]


# ---------------------------------------------------------------------------
# PlaybookRegistry selection
# ---------------------------------------------------------------------------


def test_registry_picks_lowest_priority_among_matches():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_playbook(d / "high.json", {
            "id": "match_high_priority",
            "name": "high",
            "priority": 100,
            "match": {"source_system": "zabbix"},
            "steps": [{"id": "s", "kind": "hook", "hook": "x"}],
        })
        _write_playbook(d / "low.json", {
            "id": "match_low_priority",
            "name": "low",
            "priority": 10,
            "match": {"source_system": "zabbix"},
            "steps": [{"id": "s", "kind": "hook", "hook": "x"}],
        })
        _write_playbook(d / "wild.json", {
            "id": "wildcard",
            "name": "wildcard",
            "priority": 1000,
            "match": {},
            "steps": [{"id": "s", "kind": "hook", "hook": "x"}],
        })
        reg = PlaybookRegistry(definitions_dir=d)
        chosen = reg.select({"source_system": "zabbix"})
        assert chosen is not None
        assert chosen.id == "match_low_priority"


def test_registry_falls_back_to_wildcard_when_no_specific_match():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_playbook(d / "specific.json", {
            "id": "zabbix_only",
            "name": "x",
            "priority": 10,
            "match": {"source_system": "zabbix"},
            "steps": [{"id": "s", "kind": "hook", "hook": "x"}],
        })
        _write_playbook(d / "wildcard.json", {
            "id": "wildcard",
            "name": "x",
            "priority": 1000,
            "match": {},
            "steps": [{"id": "s", "kind": "hook", "hook": "x"}],
        })
        reg = PlaybookRegistry(definitions_dir=d)
        chosen = reg.select({"source_system": "ELK"})
        assert chosen is not None
        assert chosen.id == "wildcard"


def test_registry_severity_range_match_includes_and_excludes():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_playbook(d / "low_only.json", {
            "id": "low_severity_only",
            "name": "x",
            "priority": 10,
            "match": {"severity_max": "warning"},
            "steps": [{"id": "s", "kind": "hook", "hook": "x"}],
        })
        reg = PlaybookRegistry(definitions_dir=d)
        # 'info' is rank 0 <= warning rank 2  -> match
        assert reg.select({"severity": "info"}) is not None
        # 'critical' rank 4 > warning rank 2 -> no match (no wildcard fallback either)
        assert reg.select({"severity": "critical"}) is None


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_playbook_rejects_duplicate_step_ids():
    with pytest.raises(ValueError, match="Duplicate"):
        Playbook.from_dict({
            "id": "x",
            "name": "x",
            "steps": [
                {"id": "a", "kind": "hook", "hook": "h"},
                {"id": "a", "kind": "hook", "hook": "h"},
            ],
        })


def test_playbookstep_agent_requires_agent_field():
    with pytest.raises(ValueError, match="must declare 'agent'"):
        PlaybookStep(id="x", kind=StepKind.AGENT).validate()


def test_playbookstep_hook_requires_hook_field():
    with pytest.raises(ValueError, match="must declare 'hook'"):
        PlaybookStep(id="x", kind=StepKind.HOOK).validate()


def test_playbookstep_loop_requires_substeps():
    with pytest.raises(ValueError, match="non-empty steps"):
        PlaybookStep(id="x", kind=StepKind.LOOP, max_iterations=2).validate()


# ---------------------------------------------------------------------------
# Default playbook integrity — protects against accidental edits to the
# shipped pipelines/definitions/default.json.
# ---------------------------------------------------------------------------


def test_default_playbook_loads_with_expected_structure():
    from pipelines.registry import playbook_registry

    default = playbook_registry.get("default_v1")
    assert default is not None
    assert default.priority == 1000  # wildcard fallback rank
    # The current pipeline has 14 top-level steps; this guards against drift.
    assert len(default.steps) == 14

    loop = next((s for s in default.steps if s.id == "insight_loop"), None)
    assert loop is not None
    assert loop.kind == StepKind.LOOP
    assert loop.max_iterations == 2
    assert loop.break_predicate == "insight_loop_should_break"
    # The widen substep must be predicate-gated so it doesn't run on the final iteration.
    widen = next((s for s in loop.steps if s.id == "widen_runtime"), None)
    assert widen is not None
    assert widen.predicate == "should_widen_runtime"


# ---------------------------------------------------------------------------
# Phase 3.5 — fault-type playbook selection
# ---------------------------------------------------------------------------


def test_registry_selects_lightweight_for_low_severity_log_signal():
    from pipelines.registry import playbook_registry

    pb = playbook_registry.select({"source_category": "log_signal", "severity": "warning"})
    assert pb is not None
    assert pb.id == "log_signal_lightweight"


def test_registry_selects_critical_incident_for_critical_severity():
    from pipelines.registry import playbook_registry

    pb = playbook_registry.select({"severity": "critical"})
    assert pb is not None
    assert pb.id == "critical_incident"


def test_registry_selects_default_for_unmatched_attrs():
    from pipelines.registry import playbook_registry

    pb = playbook_registry.select({"source_category": "zabbix_alert", "severity": "high"})
    assert pb is not None
    assert pb.id == "default_v1"


def test_lightweight_playbook_skips_historical_and_loop():
    from pipelines.registry import playbook_registry

    pb = playbook_registry.get("log_signal_lightweight")
    assert pb is not None
    step_ids = {s.id for s in pb.steps}
    assert "historical" not in step_ids
    assert "find_similar_cases" not in step_ids
    # single insight agent step, not a loop
    insight = next((s for s in pb.steps if s.id == "insight"), None)
    assert insight is not None and insight.kind == StepKind.AGENT


def test_critical_playbook_runs_three_insight_rounds():
    from pipelines.registry import playbook_registry

    pb = playbook_registry.get("critical_incident")
    assert pb is not None
    loop = next((s for s in pb.steps if s.id == "insight_loop"), None)
    assert loop is not None and loop.kind == StepKind.LOOP
    assert loop.max_iterations == 3
