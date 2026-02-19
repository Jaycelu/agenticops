from typing import Any, Dict, List

import yaml

from models.automation import AlertEvent


class PlaybookDraftService:
    """Generate and validate ansible playbook drafts in observe-only workflow."""

    def _recommended_commands(self, event: AlertEvent) -> List[str]:
        text = f"{event.name or ''} {(event.payload or {}).get('event_type', '')}".lower()
        if "ospf" in text or "neighbor" in text:
            return [
                "display ospf peer",
                "display ospf interface",
                "display ip routing-table protocol ospf",
            ]
        if "interface" in text or "link" in text or "down" in text:
            return [
                "display interface brief",
                "display interface counters errors",
                "display transceiver diagnosis interface",
            ]
        return [
            "display current-configuration | include hostname",
            "display alarm active",
            "display logbuffer | include ERROR|DOWN|OSPF|BGP",
        ]

    def _build_yaml_text(self, event: AlertEvent) -> str:
        playbook_obj = [
            {
                "name": f"Diagnostic draft for event {event.id}",
                "hosts": "network_devices",
                "gather_facts": False,
                "vars": {
                    "event_id": event.id,
                    "event_source": event.source,
                    "event_name": event.name,
                    "event_severity": event.severity,
                },
                "tasks": [
                    {
                        "name": "Print execution context",
                        "ansible.builtin.debug": {
                            "msg": "observe-only playbook draft; no config changes will be executed"
                        },
                    },
                    {
                        "name": "Run read-only diagnostics",
                        "ansible.builtin.command": "{{ item }}",
                        "loop": self._recommended_commands(event),
                        "register": "diagnostic_output",
                        "changed_when": False,
                    },
                    {
                        "name": "Show summarized outputs",
                        "ansible.builtin.debug": {
                            "var": "diagnostic_output.results"
                        },
                    },
                ],
            }
        ]
        return yaml.safe_dump(playbook_obj, sort_keys=False, allow_unicode=False)

    def validate_draft(self, playbook_yaml: str) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []
        parsed: Any = None
        try:
            parsed = yaml.safe_load(playbook_yaml)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"YAML parse failed: {exc}")
            return {"passed": False, "errors": errors, "warnings": warnings}

        if not isinstance(parsed, list) or not parsed:
            errors.append("Playbook root must be a non-empty list")
            return {"passed": False, "errors": errors, "warnings": warnings}

        play = parsed[0]
        if not isinstance(play, dict):
            errors.append("First play must be an object")
            return {"passed": False, "errors": errors, "warnings": warnings}

        if not play.get("hosts"):
            errors.append("Missing required field: hosts")
        tasks = play.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            errors.append("Missing required field: tasks (non-empty list)")
        else:
            for idx, task in enumerate(tasks):
                if not isinstance(task, dict):
                    errors.append(f"Task[{idx}] must be an object")
                    continue
                module_keys = [k for k in task.keys() if "." in k]
                if not module_keys:
                    warnings.append(f"Task[{idx}] has no FQCN module key")

        return {"passed": not errors, "errors": errors, "warnings": warnings}

    def generate_for_event(self, event: AlertEvent) -> Dict[str, Any]:
        playbook_yaml = self._build_yaml_text(event)
        check = self.validate_draft(playbook_yaml)
        return {"playbook_yaml": playbook_yaml, "check": check}


playbook_draft_service = PlaybookDraftService()

