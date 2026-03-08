from __future__ import annotations

from typing import Any, Dict, List


class RemediationRecommendationService:
    """Generates prioritized actions from root-cause oriented signals."""

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

        actions: List[Dict[str, Any]] = []

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

        if any(token in root for token in ["链路", "接口"]) or family in {"crc", "interface", "flap", "link"}:
            add(1, "topology_trace", "优先检查上下联链路", "当前信号更像链路或接口问题，应先确认对端和物理连接。")
            add(2, "alert_correlation", "对齐 Zabbix 相关告警", "确认是否存在接口 down、errors、availability 类告警。")
            add(3, "ticket_or_change", "准备人工维护或变更窗口", "链路类问题通常需要人工维护确认，避免直接自动执行。")
        elif any(token in root for token in ["邻居", "路由"]) or family in {"neighbor", "routing", "ospf", "bgp"}:
            add(1, "topology_neighbors", "检查邻接和路由关系", "当前信号更像邻居关系或路由稳定性异常。")
            add(2, "blast_radius", "评估相邻设备影响面", "优先确认是否存在同站点或相邻设备的连锁异常。")
            add(3, "ticket_or_change", "准备网络侧人工处置", "邻居/路由类问题通常需要人工维护确认。")
        elif any(token in root for token in ["硬件", "光模块"]) or family in {"hardware", "fan", "power", "temperature"}:
            add(1, "hardware_validation", "核查硬件与模块状态", "当前更像硬件或光模块异常，应先确认设备健康和模块状态。")
            add(2, "spare_plan", "准备备件或替换计划", "硬件类问题通常无法依靠软件动作直接恢复。")
            add(3, "ticket_only", "转人工工单处理", "硬件问题优先走工单和现场维护闭环。")
        elif any(token in root for token in ["认证", "安全"]) or family in {"auth", "security"}:
            add(1, "security_review", "检查认证与访问控制策略", "当前信号更像认证失败或安全策略异常。")
            add(2, "alert_correlation", "核对同设备安全告警", "确认是否存在重复失败、锁定或 ACL 命中。")
            add(3, "ticket_only", "转安全/网络协同工单", "该类问题建议按审批流程人工介入。")
        else:
            add(1, "cross_source_review", "先做跨源证据复核", "当前根因仍较泛化，先复核日志、告警和资产上下文。")
            add(2, "blast_radius", "确认影响面", "优先明确是否为单设备异常还是站点级问题。")
            add(3, "ticket_only", "必要时转人工工单", "证据不足时不建议直接执行修复动作。")

        if cross_source:
            add(4, "confidence_boost", "优先处理跨源确认问题", "日志与监控已双重确认，可优先排在待处置队列前列。", mode="queue_priority")

        if scope == "topology_wide":
            add(5, "site_blast_radius", "扩大站点影响面检查", "当前影响面可能覆盖核心路径或多个下游设备。")
        elif scope == "adjacent_devices":
            add(5, "adjacent_review", "同步检查相邻设备", "当前问题已影响到相邻设备或链路。")

        if incident_priority in {"P1", "P2"}:
            add(6, "fast_escalation", "提高处置优先级", f"当前事件优先级为 {incident_priority}，建议进入加急处置队列。", mode="queue_priority")

        actions.sort(key=lambda item: (item["priority_order"], item["title"]))
        return actions


remediation_recommendation_service = RemediationRecommendationService()
