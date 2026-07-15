from __future__ import annotations

from typing import Any, Dict
import re

from database import SessionLocal
from probes.ssh_transport import ssh_probe_transport
from probes.redaction import redact_output
from services.execution_engine import ExecutionStatus, Executor, ExecutorType


class SSHMutationExecutor(Executor):
    _FORBIDDEN = re.compile(r"(?i)(?:\r|\n|password|secret|community|private-key|pre-shared-key)")
    def __init__(self) -> None:
        super().__init__(ExecutorType.SSH)

    def validate_config(self, action_config: Dict[str, Any]) -> bool:
        commands = action_config.get("commands")
        return bool(
            isinstance(commands, list)
            and commands
            and all(
                isinstance(command, str)
                and 0 < len(command) <= 1000
                and not self._FORBIDDEN.search(command)
                for command in commands
            )
            and isinstance(action_config.get("credential_id"), int)
            and isinstance(action_config.get("netbox_device_id"), int)
        )

    async def execute(self, task_id: int, action_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        del task_id, context
        if not self.validate_config(action_config):
            return {"status": ExecutionStatus.FAILED.value, "message": "invalid SSH mutation configuration"}
        db = SessionLocal()
        try:
            target = ssh_probe_transport.resolve_target(
                db,
                action_config["credential_id"],
                action_config["netbox_device_id"],
                required_scope="device.mutate",
            )
            results = ssh_probe_transport.execute(
                target,
                list(action_config["commands"]),
                int(action_config.get("timeout") or 60),
            )
            for item in results:
                item["output"] = redact_output(str(item.get("output") or ""), max_bytes=262144)[0]
                item["stderr"] = redact_output(str(item.get("stderr") or ""), max_bytes=262144)[0]
            failed = [item for item in results if item.get("exit_status") not in (0, None)]
            return {
                "status": ExecutionStatus.FAILED.value if failed else ExecutionStatus.SUCCESS.value,
                "message": "SSH mutation completed" if not failed else "SSH mutation command failed",
                "details": {"results": results},
            }
        except Exception as exc:
            return {
                "status": ExecutionStatus.FAILED.value,
                "message": "SSH mutation failed",
                "error": type(exc).__name__,
            }
        finally:
            db.close()


ssh_mutation_executor = SSHMutationExecutor()
