"""Compatibility executor that deliberately refuses direct webhook delivery.

All production notifications must be written to the transactional generic webhook
outbox by ``ExecutionService``. Keeping this non-networking adapter avoids silently
reviving the historical action-supplied URL path through old imports.
"""
from __future__ import annotations

from typing import Any, Dict

from services.execution_engine import ExecutionStatus, Executor, ExecutorType


class NotificationExecutor(Executor):
    def __init__(self) -> None:
        super().__init__(ExecutorType.NOTIFICATION)

    async def execute(self, task_id: int, action_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        del task_id, action_config, context
        return {
            "status": ExecutionStatus.FAILED.value,
            "message": "direct notification delivery is disabled; use the webhook outbox",
            "error": "direct_webhook_disabled",
        }

    def validate_config(self, action_config: Dict[str, Any]) -> bool:
        del action_config
        return False


notification_executor = NotificationExecutor()
