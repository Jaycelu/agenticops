"""Phase 3 — Pipeline as Code.

声明式 playbook + 轻量执行器，把 case_orchestrator 里硬编码的 agent 顺序抽成 JSON。
对外暴露 schemas / registry / engine 三个子模块。
"""
from pipelines.engine import PipelineEngine
from pipelines.registry import PlaybookRegistry, playbook_registry
from pipelines.schemas import (
    Playbook,
    PlaybookStep,
    PipelineState,
    StepKind,
)

__all__ = [
    "Playbook",
    "PlaybookStep",
    "PipelineState",
    "StepKind",
    "PipelineEngine",
    "PlaybookRegistry",
    "playbook_registry",
]
