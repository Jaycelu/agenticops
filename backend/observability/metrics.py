from __future__ import annotations

import threading
from collections import defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        key = (name, tuple(sorted((key, str(item)) for key, item in labels.items())))
        with self._lock:
            self._counters[key] += value

    def render(self, gauges: dict[str, float] | None = None) -> str:
        lines: list[str] = []
        with self._lock:
            rows = sorted(self._counters.items())
        seen: set[str] = set()
        for (name, labels), value in rows:
            if name not in seen:
                lines.append(f"# TYPE {name} counter")
                seen.add(name)
            label_text = "{" + ",".join(f'{key}="{self._escape(item)}"' for key, item in labels) + "}" if labels else ""
            lines.append(f"{name}{label_text} {value}")
        for name, value in sorted((gauges or {}).items()):
            lines.extend((f"# TYPE {name} gauge", f"{name} {value}"))
        return "\n".join(lines) + "\n"

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


metrics_registry = MetricsRegistry()
