"""
拓扑感知 + SSH实测 的多阶段研判服务
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config.settings import settings
from mcp.netbox_mcp import NetBoxMCP
from models.llm_client import LLMClient
from services.ssh_service import ssh_service
from services.command_template_service import command_template_service

logger = logging.getLogger(__name__)


class ContextAwareDiagnosisService:
    def __init__(self):
        self.llm_client = LLMClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_url,
            model=settings.llm_model_name,
        )
        self.netbox_mcp = NetBoxMCP()

    async def run(
        self,
        db: Session,
        site_id: int,
        netbox_device_id: Optional[int],
        abnormal_type: str,
        source_logs: Dict[str, Any],
        credential_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        topology_context = await self._build_topology_context(netbox_device_id)

        step1 = await self._step1_hypothesis(
            site_id=site_id,
            abnormal_type=abnormal_type,
            source_logs=source_logs,
            topology_context=topology_context,
        )

        inspection = {
            "commands": [],
            "outputs": [],
            "status": "skipped",
            "error": "no_credential_bound",
            "template_match": None,
        }
        if credential_id and netbox_device_id:
            template_type = self._select_template_type(step1)
            resolved = await command_template_service.resolve_commands_for_device(
                db,
                device_id=netbox_device_id,
                template_type=template_type,
            )
            inspection["template_match"] = resolved
            if resolved.get("found"):
                commands = resolved.get("commands") or []
            else:
                commands = []

            if not commands:
                inspection = {
                    "commands": [],
                    "outputs": [],
                    "status": "manual_required",
                    "error": resolved.get("reason") or "missing_vendor_template",
                    "template_match": resolved,
                }
            else:
                try:
                    result = ssh_service.execute_commands(
                        db,
                        credential_id=credential_id,
                        netbox_device_id=netbox_device_id,
                        commands=commands,
                    )
                    inspection = {
                        "commands": commands,
                        "outputs": result.get("results", []),
                        "status": "success",
                        "error": None,
                        "template_match": resolved,
                    }
                except Exception as exc:  # noqa: BLE001
                    inspection = {
                        "commands": commands,
                        "outputs": [],
                        "status": "failed",
                        "error": str(exc),
                        "template_match": resolved,
                    }

        step3 = await self._step3_final_conclusion(
            site_id=site_id,
            abnormal_type=abnormal_type,
            source_logs=source_logs,
            topology_context=topology_context,
            initial_hypothesis=step1,
            inspection=inspection,
        )

        audit_trail = [
            {
                "stage": "Trigger",
                "title": "告警触发",
                "payload": {
                    "site_id": site_id,
                    "netbox_device_id": netbox_device_id,
                    "abnormal_type": abnormal_type,
                    "source_logs": source_logs,
                },
            },
            {
                "stage": "Inspection",
                "title": "SSH现场检查",
                "payload": {
                    **inspection,
                    "adaptation_message": self._build_adaptation_message(inspection),
                },
            },
            {
                "stage": "Reasoning",
                "title": "AI多阶段推理",
                "payload": {
                    "initial_hypothesis": step1,
                    "topology_context": topology_context,
                },
            },
            {
                "stage": "Conclusion",
                "title": "最终结论",
                "payload": step3,
            },
        ]

        return {
            "topology_context": topology_context,
            "initial_hypothesis": step1,
            "inspection": inspection,
            "final": step3,
            "audit_trail": audit_trail,
        }

    def _select_template_type(self, initial_hypothesis: Dict[str, Any]) -> str:
        text = f"{initial_hypothesis.get('hypothesis', '')} {initial_hypothesis.get('reasoning', '')}".lower()
        if any(k in text for k in ["optic", "transceiver", "光模块", "los"]):
            return "optics_diagnosis"
        return "diagnosis_default"

    def _build_adaptation_message(self, inspection: Dict[str, Any]) -> str:
        template_match = inspection.get("template_match") or {}
        if template_match.get("found"):
            vendor = template_match.get("vendor")
            tpl = (template_match.get("template") or {}).get("name")
            return f"由于设备厂商为 [{vendor}]，已自动加载 [{tpl}] 执行命令采集。"
        return f"缺少厂商指令集，已转人工处理：{inspection.get('error')}"

    async def _build_topology_context(self, netbox_device_id: Optional[int]) -> Dict[str, Any]:
        if not netbox_device_id:
            return {"device": {}, "links": []}

        device_info = await self.netbox_mcp.execute({"action": "get_device_by_id", "device_id": netbox_device_id})
        topology_info = await self.netbox_mcp.execute({"action": "get_device_topology", "device_id": netbox_device_id})

        return {
            "device": device_info.data if device_info.success else {},
            "links": topology_info.data.get("links", []) if topology_info.success and topology_info.data else [],
        }

    async def _step1_hypothesis(
        self,
        site_id: int,
        abnormal_type: str,
        source_logs: Dict[str, Any],
        topology_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        system_prompt = (
            "你是网络运维研判引擎。先做初步假设，不要直接下最终结论。"
            "需要综合日志+设备角色+平台+链路对端信息。"
            "输出JSON: hypothesis, suspected_domain(physical/config/peer/other), confidence(0-1), recommended_commands(数组), reasoning。"
        )
        user_payload = {
            "site_id": site_id,
            "abnormal_type": abnormal_type,
            "source_logs": source_logs,
            "topology_context": topology_context,
        }
        return await self._chat_json(system_prompt, user_payload, fallback={
            "hypothesis": "可能为链路或配置问题，需要SSH实测",
            "suspected_domain": "other",
            "confidence": 0.4,
            "recommended_commands": ssh_service.build_diagnostic_commands(
                topology_context.get("device", {}).get("platform"),
                topology_context.get("device", {}).get("manufacturer"),
            ),
            "reasoning": "初始信息不足，进入设备进一步确认",
        })

    async def _step3_final_conclusion(
        self,
        site_id: int,
        abnormal_type: str,
        source_logs: Dict[str, Any],
        topology_context: Dict[str, Any],
        initial_hypothesis: Dict[str, Any],
        inspection: Dict[str, Any],
    ) -> Dict[str, Any]:
        system_prompt = (
            "你是网络故障根因分析专家。必须将SSH实测输出与日志、拓扑进行交叉验证后再结论。"
            "禁止只根据日志或只根据拓扑下判断。"
            "输出JSON: root_cause_type(hardware/configuration/peer/unknown), severity(low/medium/high/critical), "
            "summary, reasoning, recommendations(数组), action_type(replace_hardware/config_optimization/manual_investigation), confidence(0-1)。"
        )
        user_payload = {
            "site_id": site_id,
            "abnormal_type": abnormal_type,
            "source_logs": source_logs,
            "topology_context": topology_context,
            "initial_hypothesis": initial_hypothesis,
            "ssh_inspection": inspection,
        }
        return await self._chat_json(system_prompt, user_payload, fallback={
            "root_cause_type": "unknown",
            "severity": "medium",
            "summary": "已完成多源分析，但证据不足以确定单一根因",
            "reasoning": "请补充设备现场检查数据后再确认",
            "recommendations": ["补充接口物理层数据", "检查对端同口计数器", "人工复核最近配置变更"],
            "action_type": "manual_investigation",
            "confidence": 0.45,
        })

    async def _chat_json(self, system_prompt: str, payload: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.llm_client.chat_completion_with_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.2,
                timeout=45.0,
            )
            return response if isinstance(response, dict) else fallback
        except Exception as exc:  # noqa: BLE001
            logger.warning("context-aware diagnosis chat failed: %s", exc)
            return fallback


context_aware_diagnosis_service = ContextAwareDiagnosisService()
