"""Playbook / Step / State 数据契约。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class StepKind(str, Enum):
    AGENT = "agent"        # 调用某个已注册 agent
    HOOK = "hook"          # 调用 orchestrator 暴露的具名 Python 钩子
    LOOP = "loop"          # 顺序执行 substeps，最多 max_iterations 次


@dataclass
class PlaybookStep:
    id: str
    kind: StepKind
    # AGENT 专属
    agent: Optional[str] = None
    # HOOK 专属
    hook: Optional[str] = None
    # 通用：跳过逻辑（None / 缺失 = 不跳过）
    predicate: Optional[str] = None
    # LOOP 专属
    max_iterations: int = 1
    break_predicate: Optional[str] = None
    steps: List["PlaybookStep"] = field(default_factory=list)
    # 失败时的处理：continue / stop（暂未支持 escalate，留 hook 实现）
    on_failure: str = "continue"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaybookStep":
        kind = StepKind(str(data.get("kind") or "").lower())
        return cls(
            id=str(data["id"]),
            kind=kind,
            agent=data.get("agent"),
            hook=data.get("hook"),
            predicate=data.get("predicate"),
            max_iterations=int(data.get("max_iterations") or 1),
            break_predicate=data.get("break_predicate"),
            steps=[PlaybookStep.from_dict(item) for item in data.get("steps") or []],
            on_failure=str(data.get("on_failure") or "continue"),
        )

    def validate(self) -> None:
        if self.kind == StepKind.AGENT and not self.agent:
            raise ValueError(f"AGENT step '{self.id}' must declare 'agent'")
        if self.kind == StepKind.HOOK and not self.hook:
            raise ValueError(f"HOOK step '{self.id}' must declare 'hook'")
        if self.kind == StepKind.LOOP:
            if self.max_iterations < 1:
                raise ValueError(f"LOOP step '{self.id}' must have max_iterations >= 1")
            if not self.steps:
                raise ValueError(f"LOOP step '{self.id}' must have non-empty steps")
            for sub in self.steps:
                sub.validate()


@dataclass
class Playbook:
    id: str
    name: str
    match: Dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    steps: List[PlaybookStep] = field(default_factory=list)
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playbook":
        playbook = cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            match=dict(data.get("match") or {}),
            priority=int(data.get("priority") or 100),
            steps=[PlaybookStep.from_dict(item) for item in data.get("steps") or []],
            description=str(data.get("description") or ""),
        )
        playbook.validate()
        return playbook

    def validate(self) -> None:
        if not self.id:
            raise ValueError("Playbook.id is required")
        if not self.steps:
            raise ValueError(f"Playbook '{self.id}' must have at least one step")
        seen: set[str] = set()
        for step in self.steps:
            step.validate()
            if step.id in seen:
                raise ValueError(f"Duplicate step id in playbook '{self.id}': {step.id}")
            seen.add(step.id)


@dataclass
class PipelineState:
    """
    Playbook 执行期间在各 step / hook 之间传递的可变状态。

    case / context 来自 orchestrator；runs / claims / remediation_plan 由 step 累积；
    extras 给 hook 临时存放跨 step 数据（如 loop_iter / query_spec / similar_cases），
    trace 是审计轨迹。
    """

    db: Any  # SQLAlchemy Session（无类型约束以避免 dataclass 与 ORM 的耦合）
    case: Any  # CaseRecord
    context: Any  # AgentExecutionContext
    runs: List[Any] = field(default_factory=list)
    claims: List[Any] = field(default_factory=list)
    remediation_plan: Optional[Any] = None
    extras: Dict[str, Any] = field(default_factory=dict)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    critic_decision: Optional[str] = None


# Hook / Predicate / ExecuteAgentFn 的类型别名（仅供阅读，不强制运行时检查）。
HookFn = Callable[[PipelineState], Any]            # 可为同步 / 异步；engine 会用 inspect 判断
PredicateFn = Callable[[PipelineState], bool]
ExecuteAgentFn = Callable[[PipelineState, Any], Any]
