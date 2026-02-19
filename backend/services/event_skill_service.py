from typing import Any, Dict

from models.automation import AlertEvent
from services.schemas import DecisionResult, DiagnosisResult, DiagnosisType, Evidence, SeverityLevel


class EventSkillService:
    """Route event signals to read-only diagnostic skills."""

    def _normalize_text(self, event: AlertEvent) -> str:
        return f"{event.name or ''} {(event.payload or {}).get('event_type', '')}".lower()

    def _route_skill(self, event: AlertEvent) -> Dict[str, Any]:
        text = self._normalize_text(event)
        if "ospf" in text or "neighbor" in text:
            return {
                "skill_code": "ospf_neighbor_check_skill",
                "diagnosis_type": DiagnosisType.NEIGHBOR_UNSTABLE,
                "summary": "检测到OSPF邻居异常，建议执行只读邻居状态检查。",
                "recommendations": [
                    "show ip ospf neighbor",
                    "show ip ospf interface brief",
                    "比对对端邻居状态与hello/dead定时参数",
                ],
            }
        if "interface" in text or "link" in text or "down" in text:
            return {
                "skill_code": "interface_health_check_skill",
                "diagnosis_type": DiagnosisType.INTERFACE_FLAP,
                "summary": "检测到接口异常，建议执行只读接口健康检查。",
                "recommendations": [
                    "show interface counters errors",
                    "show interface status",
                    "检查光模块与对端接口错误计数",
                ],
            }
        return {
            "skill_code": "asset_context_skill",
            "diagnosis_type": DiagnosisType.UNKNOWN,
            "summary": "事件类型未命中专用规则，建议执行资产与拓扑上下文补全。",
            "recommendations": [
                "查询NetBox设备与拓扑关系",
                "结合事件原始日志做人审",
            ],
        }

    def build_decision_for_event(self, event: AlertEvent) -> Dict[str, Any]:
        routed = self._route_skill(event)
        severity_map = {
            5: SeverityLevel.CRITICAL,
            4: SeverityLevel.HIGH,
            3: SeverityLevel.HIGH,
            2: SeverityLevel.WARNING,
            1: SeverityLevel.LOW,
            0: SeverityLevel.LOW,
        }
        risk_level = severity_map.get(event.severity_level, SeverityLevel.WARNING)
        confidence = 0.75 if routed["diagnosis_type"] != DiagnosisType.UNKNOWN else 0.55

        decision = DecisionResult(
            rule_id=f"EVENT_SKILL_{routed['skill_code']}",
            rule_name=f"事件路由-{routed['skill_code']}",
            diagnosis=DiagnosisResult(
                diagnosis_type=routed["diagnosis_type"],
                severity=risk_level,
                confidence=confidence,
                summary=routed["summary"],
                evidence=[
                    Evidence(type="event_id", value=event.id, description="事件ID"),
                    Evidence(type="event_source", value=event.source, description="事件来源"),
                    Evidence(type="event_name", value=event.name, description="事件名称"),
                ],
                recommendations=routed["recommendations"],
                risk_level=risk_level,
                require_human_confirm=True,
            ),
            context={
                "event_id": event.id,
                "event_source": event.source,
                "event_name": event.name,
                "device_ip": event.host or "unknown",
                "site_id": event.site_id,
                "netbox_device_id": event.netbox_device_id,
                "recommended_skill_code": routed["skill_code"],
                "read_only": True,
            },
        )

        audit_trail = [
            {
                "stage": "Trigger",
                "title": "事件触发",
                "payload": {
                    "event_id": event.id,
                    "source": event.source,
                    "name": event.name,
                    "severity": event.severity,
                },
            },
            {
                "stage": "Reasoning",
                "title": "只读Skill路由",
                "payload": {
                    "skill_code": routed["skill_code"],
                    "summary": routed["summary"],
                },
            },
            {
                "stage": "Conclusion",
                "title": "生成只读研判任务",
                "payload": {
                    "observe_only": True,
                    "require_human_confirm": True,
                },
            },
        ]

        return {"decision": decision, "audit_trail": audit_trail}


event_skill_service = EventSkillService()
