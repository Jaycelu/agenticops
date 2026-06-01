from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


class RemediationRecommendationService:
    """Generates prioritized actions from root-cause oriented signals (policy JSON + harness audit)."""

    def __init__(self) -> None:
        self.last_policy_audit: Dict[str, Any] = {}

    def _policy_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "storage" / "remediation_policy.v1.json"

    def _load_policy(self) -> Dict[str, Any]:
        path = self._policy_path()
        if not path.exists():
            return {"version": "missing", "rules": []}
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _select_rule(self, policy: Dict[str, Any], *, family: str, root: str) -> Tuple[Dict[str, Any], str]:
        rules = list(policy.get("rules") or [])
        rules.sort(key=lambda r: int(r.get("priority") or 999))
        fam = (family or "").lower()
        root_l = (root or "").lower()
        for rule in rules:
            if self._rule_matches(rule, fam, root_l):
                return rule, str(rule.get("id") or "unknown")
        return {}, "none"

    def _rule_matches(self, rule: Dict[str, Any], family: str, root: str) -> bool:
        match = rule.get("match") or {}
        families = {str(x).lower() for x in (match.get("families") or [])}
        tokens = [str(t).lower() for t in (match.get("tokens_any") or [])]
        if families and family in families:
            return True
        if tokens and any(t in root for t in tokens if t):
            return True
        if not families and not tokens:
            return True
        return False

    def build_actions(
        self,
        *,
        root_cause: str,
        signal_family: str | None = None,
        impact_scope: str | None = None,
        priority: str | None = None,
        cross_source: bool = False,
    ) -> List[Dict[str, Any]]:
        family = (signal_family or "").lower()
        root = (root_cause or "").lower()
        scope = (impact_scope or "device_scope").lower()
        incident_priority = (priority or "P3").upper()

        policy = self._load_policy()
        rule, rule_id = self._select_rule(policy, family=family, root=root)
        base_actions: List[Dict[str, Any]] = []
        if rule.get("actions"):
            base_actions = [dict(a) for a in rule["actions"]]
        else:
            base_actions = [
                {
                    "priority_order": 1,
                    "action_type": "cross_source_review",
                    "title": "先做跨源证据复核",
                    "reason": "策略文件缺失或规则未命中，使用保守默认动作。",
                    "mode": "manual_check",
                }
            ]

        actions = list(base_actions)

        def add(
            order: int,
            action_type: str,
            title: str,
            reason: str,
            mode: str = "manual_check",
        ) -> None:
            actions.append(
                {
                    "priority_order": order,
                    "action_type": action_type,
                    "title": title,
                    "reason": reason,
                    "mode": mode,
                }
            )

        if cross_source:
            add(4, "confidence_boost", "优先处理跨源确认问题", "日志与监控已双重确认，可优先排在待处置队列前列。", mode="queue_priority")

        if scope == "topology_wide":
            add(5, "site_blast_radius", "扩大站点影响面检查", "当前影响面可能覆盖核心路径或多个下游设备。")
        elif scope == "adjacent_devices":
            add(5, "adjacent_review", "同步检查相邻设备", "当前问题已影响到相邻设备或链路。")

        if incident_priority in {"P1", "P2"}:
            add(6, "fast_escalation", "提高处置优先级", f"当前事件优先级为 {incident_priority}，建议进入加急处置队列。", mode="queue_priority")

        actions.sort(key=lambda item: (item["priority_order"], item["title"]))

        # Phase 1.5: every action self-describes a tool_id so the execution closed loop
        # (execution_service.execute_plan) can classify it. Advisory actions resolve to
        # 'manual.review' (non-executable -> skipped, not failed). A policy rule may
        # declare an explicit tool_id to opt an action into real execution.
        for action in actions:
            if not action.get("tool_id"):
                action["tool_id"] = self._infer_tool_id(action)

        self.last_policy_audit = {
            "policy_version": policy.get("version"),
            "matched_rule_id": rule_id,
            "policy_path": str(self._policy_path()),
            "policy_file_exists": self._policy_path().exists(),
        }
        return actions

    @staticmethod
    def _infer_tool_id(action: Dict[str, Any]) -> str:
        """
        从 action 的 mode / action_type 推断 tool_id。

        默认 manual.review（advisory，非可执行 -> 执行闭环里记为 skipped）。
        仅当 mode/action_type 明确指向可执行工具时才映射到 notify/api/script。
        """
        explicit = action.get("tool_id")
        if explicit:
            return str(explicit)
        mode = str(action.get("mode") or "").lower()
        action_type = str(action.get("action_type") or "").lower()
        if mode in {"notify", "notification"} or "notif" in action_type:
            return "notify.dingtalk"
        if mode == "api" or action_type in {"api", "api_request"}:
            return "api.request"
        if mode == "script" or action_type in {"script", "script_run"}:
            return "script.run"
        return "manual.review"


remediation_recommendation_service = RemediationRecommendationService()
