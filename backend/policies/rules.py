from __future__ import annotations

from typing import Any, Dict


CORE_ROLE_TOKENS = ("core", "spine", "border", "gateway", "核心", "出口", "网关")


def is_core_target(target: Dict[str, Any]) -> bool:
    haystack = " ".join(
        str(target.get(key) or "")
        for key in ("role", "device_role", "device_name", "host", "tags")
    ).lower()
    return any(token in haystack for token in CORE_ROLE_TOKENS)


def rule_snapshot(target: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "core_target": is_core_target(target),
        "target_keys": sorted(target.keys()),
    }
