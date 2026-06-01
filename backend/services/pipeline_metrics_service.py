"""
最小可观测性：追加写入 JSONL，供日志采集或简易驾驶舱解析（与 DB 解耦）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PipelineMetricsService:
    """Append-only JSONL metrics under project storage/."""

    def __init__(self) -> None:
        self._path = Path(__file__).resolve().parents[2] / "storage" / "pipeline_metrics.jsonl"

    def record(self, event_type: str, payload: Dict[str, Any]) -> None:
        line = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **payload,
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("pipeline_metrics write failed: %s", exc)


pipeline_metrics_service = PipelineMetricsService()
