from typing import Dict, List

from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from models.agenticops import AgentType


class AlertTriageAgent(BaseOpsAgent):
    agent_type = AgentType.TRIAGE
    agent_name = "Alert Triage Agent"

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        evidence_refs: List[Dict[str, str]] = []
        log_summary = context.runtime.get("log_summary") or {}
        source_payload = context.source_payload or {}
        severity = str(source_payload.get("severity") or context.normalized_payload.get("severity") or "warning").lower()

        if log_summary:
            evidence_refs.append({"type": "log_summary", "ref": "runtime.log_summary"})
        if context.evidence_items:
            evidence_refs.extend(
                {"type": item.get("evidence_type", "evidence"), "ref": str(item.get("id"))}
                for item in context.evidence_items[:5]
            )

        top_devices = (log_summary.get("devices") or [])[:3]
        hot_devices = [
            {
                "device_ip": item.get("device_ip"),
                "device_name": item.get("device_name"),
                "total_logs": item.get("total_logs"),
            }
            for item in top_devices
        ]
        classification = "event"
        if log_summary.get("summary", {}).get("total_logs"):
            classification = "log_burst"
        if context.source_system.lower() == "zabbix":
            classification = "monitoring_alert"

        priority = "P3"
        if severity in {"critical", "high"}:
            priority = "P1"
        elif severity in {"warning", "medium"}:
            priority = "P2"

        gaps = []
        if not context.netbox_device_id and not context.device_ip:
            gaps.append("缺少明确设备标识，后续诊断可能只能停留在站点级")
        if context.source_system.lower() == "zabbix" and not context.runtime.get("zabbix_alerts"):
            gaps.append("未取到 Zabbix 实时告警详情")

        summary = f"已完成初步分诊，分类为 {classification}，优先级 {priority}。"
        if hot_devices:
            summary += f" 当前最活跃设备 {hot_devices[0]['device_ip']}，日志量 {hot_devices[0]['total_logs']}。"

        return AgentDecision(
            summary=summary,
            confidence=0.82 if evidence_refs else 0.55,
            claim_type="triage_assessment",
            claim_text=summary,
            status="supported",
            evidence_refs=evidence_refs,
            gaps=gaps,
            output_payload={
                "classification": classification,
                "priority": priority,
                "severity": severity,
                "hot_devices": hot_devices,
                "requires_topology": bool(context.netbox_device_id),
                "requires_execution_channel": False,
            },
            metadata={"priority": priority},
        )


alert_triage_agent = AlertTriageAgent()
