"""PlaybookRegistry：从 definitions/*.json 加载 + 按 case 属性 select。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pipelines.schemas import Playbook


# severity ordering for severity_min / severity_max selectors
_SEVERITY_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "warning": 2,
    "high": 3,
    "critical": 4,
    "emergency": 5,
}


def _severity_rank(value: Optional[str]) -> int:
    if value is None:
        return 0
    return _SEVERITY_ORDER.get(str(value).lower(), 0)


class PlaybookRegistry:
    """
    在 import 时一次性加载 definitions/ 目录下的所有 *.json playbook。
    select(case_attrs) 返回 match 通过且 priority 最高（最小数值）的 playbook。
    """

    def __init__(self, definitions_dir: Optional[Path] = None) -> None:
        self.definitions_dir = definitions_dir or (Path(__file__).parent / "definitions")
        self._playbooks: Dict[str, Playbook] = {}
        self.load()

    # ---------------------------------------------------------------- load

    def load(self) -> None:
        self._playbooks = {}
        if not self.definitions_dir.exists():
            return
        for path in sorted(self.definitions_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            playbook = Playbook.from_dict(raw)
            if playbook.id in self._playbooks:
                raise ValueError(f"Duplicate playbook id '{playbook.id}' in {path.name}")
            self._playbooks[playbook.id] = playbook

    def reload(self) -> None:
        self.load()

    # ---------------------------------------------------------------- query

    def get(self, playbook_id: str) -> Optional[Playbook]:
        return self._playbooks.get(playbook_id)

    def all(self) -> List[Playbook]:
        return list(self._playbooks.values())

    # ---------------------------------------------------------------- select

    def select(self, case_attrs: Dict[str, Any]) -> Optional[Playbook]:
        """
        在所有已加载 playbook 中选 match 通过且 priority 最小的那一个。
        match 为空 dict 视为通配。
        """
        candidates = [p for p in self._playbooks.values() if self._match(p, case_attrs)]
        if not candidates:
            return None
        candidates.sort(key=lambda p: (p.priority, p.id))
        return candidates[0]

    @staticmethod
    def _match(playbook: Playbook, attrs: Dict[str, Any]) -> bool:
        match = playbook.match or {}
        if not match:
            return True

        # equality selectors
        for key in ("source_system", "source_category", "signal_family", "priority"):
            if key in match and match[key] is not None:
                want = match[key]
                if isinstance(want, (list, tuple, set)):
                    if attrs.get(key) not in want:
                        return False
                elif attrs.get(key) != want:
                    return False

        # severity range selectors
        if "severity_min" in match:
            if _severity_rank(attrs.get("severity")) < _severity_rank(match["severity_min"]):
                return False
        if "severity_max" in match:
            if _severity_rank(attrs.get("severity")) > _severity_rank(match["severity_max"]):
                return False

        # observe_only selector (true/false)
        if "observe_only" in match:
            if bool(attrs.get("observe_only", True)) != bool(match["observe_only"]):
                return False

        return True


# Module-level singleton; orchestrator imports this directly.
playbook_registry = PlaybookRegistry()
