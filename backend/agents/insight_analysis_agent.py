import json
from typing import Any, Dict, List

from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from config.settings import settings
from models.agenticops import AgentType
from models.llm_client import LLMClient


class InsightAnalysisAgent(BaseOpsAgent):
    agent_type = AgentType.INSIGHT
    agent_name = "Insight Analysis Agent"

    def __init__(self):
        self.llm_client = LLMClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_url,
            model=settings.llm_model_name,
        )

    async def _infer_with_llm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "你是网络运维根因分析智能体。只能基于提供的证据输出 JSON。"
            "如果证据不足，明确输出 unknown，并在 gaps 中说明。"
            "输出字段：root_cause, impact_scope, severity, confidence, summary, recommendations, gaps。"
        )
        try:
            result = await self.llm_client.chat_completion_with_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.1,
                timeout=45.0,
            )
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        topology = context.runtime.get("topology") or {}
        device = context.runtime.get("device") or {}
        ssh_result = context.runtime.get("ssh_result") or {}
        log_summary = context.runtime.get("log_summary") or {}

        evidence_refs: List[Dict[str, str]] = []
        if device:
            evidence_refs.append({"type": "topology_device", "ref": "runtime.device"})
        if topology:
            evidence_refs.append({"type": "topology", "ref": "runtime.topology"})
        if ssh_result:
            evidence_refs.append({"type": "ssh", "ref": "runtime.ssh_result"})
        if log_summary:
            evidence_refs.append({"type": "log_summary", "ref": "runtime.log_summary"})

        payload = {
            "case": {
                "title": context.title,
                "summary": context.summary,
                "source_system": context.source_system,
                "device_ip": context.device_ip,
                "host": context.host,
            },
            "log_summary": log_summary,
            "device": device,
            "topology": topology,
            "ssh_result": ssh_result,
            "prior_claims": context.prior_claims,
        }
        llm_result = await self._infer_with_llm(payload)

        gaps = llm_result.get("gaps") or []
        if not ssh_result:
            gaps.append("缺少 SSH 现场证据")
        if not topology:
            gaps.append("缺少拓扑上下文")

        root_cause = llm_result.get("root_cause") or "unknown"
        severity = llm_result.get("severity") or "warning"
        confidence = float(llm_result.get("confidence") or (0.72 if ssh_result or topology else 0.42))

        if root_cause == "unknown" and log_summary.get("devices"):
            top_device = log_summary["devices"][0]
            root_cause = f"device_log_pattern:{top_device.get('device_ip')}"

        summary = llm_result.get("summary") or (
            "已完成日志、拓扑、SSH 证据交叉分析，但证据仍不足以给出唯一根因。"
            if gaps
            else "已完成多源证据交叉分析。"
        )

        return AgentDecision(
            summary=summary,
            confidence=confidence,
            claim_type="root_cause_assessment",
            claim_text=summary,
            status="supported" if confidence >= 0.6 else "hypothesis",
            evidence_refs=evidence_refs,
            gaps=gaps,
            output_payload={
                "root_cause": root_cause,
                "impact_scope": llm_result.get("impact_scope") or "single_device",
                "severity": severity,
                "recommendations": llm_result.get("recommendations") or [],
                "device_context": {
                    "name": device.get("name"),
                    "role": device.get("role"),
                    "site": device.get("site"),
                },
            },
        )


insight_analysis_agent = InsightAnalysisAgent()

