"""轻量 Pipeline 执行器。

设计要点：
- 不依赖 case_orchestrator——通过传入 execute_agent_fn / hooks / predicates 反转控制。
- agent / hook 都允许是同步或异步可调用（inspect.iscoroutinefunction 自动适配）。
- predicate 同步即可（必须返回 bool）。
- LOOP 语义：先执行 steps，再判定 break_predicate；任一步本身可带 predicate 跳过。
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional

from pipelines.schemas import (
    ExecuteAgentFn,
    HookFn,
    Playbook,
    PlaybookStep,
    PipelineState,
    PredicateFn,
    StepKind,
)


class PipelineEngine:
    def __init__(
        self,
        *,
        agents: Dict[str, Any],
        hooks: Dict[str, HookFn],
        predicates: Dict[str, PredicateFn],
        execute_agent_fn: ExecuteAgentFn,
    ) -> None:
        self.agents = dict(agents)
        self.hooks = dict(hooks)
        self.predicates = dict(predicates)
        self.execute_agent_fn = execute_agent_fn

    async def execute(self, state: PipelineState, playbook: Playbook) -> PipelineState:
        state.extras.setdefault("playbook_id", playbook.id)
        for step in playbook.steps:
            await self._execute_step(state, step)
        return state

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _execute_step(self, state: PipelineState, step: PlaybookStep) -> None:
        if step.predicate and not self._eval_predicate(state, step.predicate):
            state.trace.append({"step": step.id, "kind": step.kind.value, "skipped": True, "reason": f"predicate_false:{step.predicate}"})
            return

        try:
            if step.kind == StepKind.AGENT:
                await self._execute_agent_step(state, step)
            elif step.kind == StepKind.HOOK:
                await self._execute_hook_step(state, step)
            elif step.kind == StepKind.LOOP:
                await self._execute_loop_step(state, step)
            else:
                raise ValueError(f"Unsupported step kind: {step.kind!r}")
        except Exception as exc:  # noqa: BLE001
            state.trace.append({"step": step.id, "kind": step.kind.value, "error": str(exc)})
            if step.on_failure == "stop":
                raise

    async def _execute_agent_step(self, state: PipelineState, step: PlaybookStep) -> None:
        agent = self.agents.get(step.agent or "")
        if agent is None:
            raise KeyError(f"Agent not registered: {step.agent!r}")
        await self._maybe_await(self.execute_agent_fn(state, agent))
        state.trace.append({"step": step.id, "kind": "agent", "agent": step.agent})

    async def _execute_hook_step(self, state: PipelineState, step: PlaybookStep) -> None:
        hook = self.hooks.get(step.hook or "")
        if hook is None:
            raise KeyError(f"Hook not registered: {step.hook!r}")
        await self._maybe_await(hook(state))
        state.trace.append({"step": step.id, "kind": "hook", "hook": step.hook})

    async def _execute_loop_step(self, state: PipelineState, step: PlaybookStep) -> None:
        for iter_idx in range(step.max_iterations):
            state.extras["loop_iter"] = iter_idx
            state.extras[f"loop_iter:{step.id}"] = iter_idx
            for sub in step.steps:
                await self._execute_step(state, sub)
            if step.break_predicate and self._eval_predicate(state, step.break_predicate):
                state.trace.append({"step": step.id, "kind": "loop", "broke_at": iter_idx, "via": step.break_predicate})
                break
        else:
            state.trace.append({"step": step.id, "kind": "loop", "completed_iterations": step.max_iterations})

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    def _eval_predicate(self, state: PipelineState, name: str) -> bool:
        pred = self.predicates.get(name)
        if pred is None:
            # Missing predicate is a misconfiguration; fail-closed to be safe (skip step / don't loop).
            state.trace.append({"predicate": name, "result": False, "reason": "predicate_not_registered"})
            return False
        try:
            return bool(pred(state))
        except Exception as exc:  # noqa: BLE001
            state.trace.append({"predicate": name, "result": False, "reason": f"predicate_raised:{exc}"})
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value
