from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolRequest:
    tool_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    target: Dict[str, Any] = field(default_factory=dict)
    mode: str = "observe"
    action: Dict[str, Any] = field(default_factory=dict)
    requested_by: str = "system"
    case_id: Optional[int] = None
    plan_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "params": self.params,
            "target": self.target,
            "mode": self.mode,
            "action": self.action,
            "requested_by": self.requested_by,
            "case_id": self.case_id,
            "plan_id": self.plan_id,
        }


@dataclass
class ToolResult:
    success: bool
    status: str
    message: str
    output: Any = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "output": self.output,
            "error": self.error,
            "details": self.details,
        }
