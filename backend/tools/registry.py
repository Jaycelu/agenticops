from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    name: str
    category: str
    capability: str
    executor_type: str
    risk_level: int
    modes: List[str] = field(default_factory=list)
    executable: bool = True
    allowed_commands: List[str] = field(default_factory=list)
    blocked_patterns: List[str] = field(default_factory=list)
    requires_approval: bool = False
    timeout: int = 30
    audit: bool = True
    param_schema: Dict[str, Any] = field(default_factory=dict)
    agent_selectable: bool = False
    read_only: bool = False
    target_scope: List[str] = field(default_factory=list)
    vendor_support: List[str] = field(default_factory=list)
    output_parser: Optional[str] = None
    evidence_mapper: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolSpec":
        return cls(
            tool_id=str(data["tool_id"]),
            name=str(data.get("name") or data["tool_id"]),
            category=str(data.get("category") or "unknown"),
            capability=str(data.get("capability") or "mutation"),
            executor_type=str(data.get("executor_type") or data.get("category") or "unknown"),
            risk_level=int(data.get("risk_level") or 0),
            modes=[str(item) for item in data.get("modes") or []],
            executable=bool(data.get("executable", True)),
            allowed_commands=[str(item) for item in data.get("allowed_commands") or []],
            blocked_patterns=[str(item) for item in data.get("blocked_patterns") or []],
            requires_approval=bool(data.get("requires_approval", False)),
            timeout=int(data.get("timeout") or 30),
            audit=bool(data.get("audit", True)),
            param_schema=dict(data.get("param_schema") or {}),
            # Legacy catalog entries remain non-selectable by default.
            agent_selectable=bool(data.get("agent_selectable", False)),
            read_only=bool(data.get("read_only", data.get("capability") == "read_only")),
            target_scope=[str(item) for item in data.get("target_scope") or []],
            vendor_support=[str(item).lower() for item in data.get("vendor_support") or []],
            output_parser=str(data["output_parser"]) if data.get("output_parser") else None,
            evidence_mapper=str(data["evidence_mapper"]) if data.get("evidence_mapper") else None,
        )


class ToolRegistry:
    def __init__(self, catalog_path: Optional[Path] = None) -> None:
        self.catalog_path = catalog_path or Path(__file__).with_name("catalog.json")
        self._tools: Dict[str, ToolSpec] = {}
        self.load()

    def load(self) -> None:
        with self.catalog_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        self._tools = {
            item["tool_id"]: ToolSpec.from_dict(item)
            for item in raw.get("tools", [])
            if item.get("tool_id")
        }

    def get(self, tool_id: str) -> Optional[ToolSpec]:
        return self._tools.get(tool_id)

    def list(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def agent_tools(self) -> List[ToolSpec]:
        return [item for item in self._tools.values() if item.agent_selectable and item.read_only]

    def validate_agent_selection(self, spec: ToolSpec, target: Dict[str, Any], vendor: str | None = None) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not spec.agent_selectable:
            errors.append("tool_not_agent_selectable")
        if not spec.read_only or spec.capability != "read_only":
            errors.append("tool_not_read_only")
        if spec.target_scope and not any(target.get(field) not in (None, "") for field in spec.target_scope):
            errors.append("target_out_of_scope")
        if vendor and spec.vendor_support and vendor.lower() not in spec.vendor_support and "all" not in spec.vendor_support:
            errors.append("vendor_not_supported")
        if not spec.output_parser:
            errors.append("output_parser_missing")
        if not spec.evidence_mapper:
            errors.append("evidence_mapper_missing")
        return not errors, errors

    def validate_params(self, spec: ToolSpec, params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        missing = [
            field
            for field in spec.param_schema.get("required", [])
            if params.get(field) in (None, "", [])
        ]
        if missing:
            return False, [f"missing_required:{field}" for field in missing]
        return True, []

    def command_values(self, params: Dict[str, Any]) -> List[str]:
        values: List[str] = []
        command = params.get("command")
        if command:
            values.append(str(command))
        commands = params.get("commands")
        if isinstance(commands, str):
            values.append(commands)
        elif isinstance(commands, Iterable):
            values.extend(str(item) for item in commands if item is not None)
        script_args = params.get("script_args")
        if isinstance(script_args, Iterable) and not isinstance(script_args, (str, bytes, dict)):
            values.extend(str(item) for item in script_args if item is not None)
        return values

    def find_blocked_patterns(self, spec: ToolSpec, params: Dict[str, Any]) -> List[str]:
        commands = self.command_values(params)
        hits: List[str] = []
        for pattern in spec.blocked_patterns:
            compiled = re.compile(pattern)
            if any(compiled.search(command) for command in commands):
                hits.append(pattern)
        return hits

    def commands_match_allowlist(self, spec: ToolSpec, params: Dict[str, Any]) -> bool:
        if not spec.allowed_commands:
            return True
        commands = self.command_values(params)
        if not commands:
            return True
        prefixes = tuple(item.lower() for item in spec.allowed_commands)
        return all(command.strip().lower().startswith(prefixes) for command in commands)


tool_registry = ToolRegistry()
