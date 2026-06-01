import json
from typing import Any, Dict, Iterable, List, Optional, Set

from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from models.agenticops import AgentType
from models.llm_client import LLMClient
from services.model_registry import build_client


class InsightAnalysisAgent(BaseOpsAgent):
    agent_type = AgentType.INSIGHT
    agent_name = "Insight Analysis Agent"

    def __init__(self):
        self.llm_client = build_client()

    async def _infer_with_llm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "你是网络运维根因分析智能体。只能基于提供的证据输出 JSON。"
            "如果证据不足，明确输出 unknown，并在 gaps 中说明。"
            "输出字段：root_cause, impact_scope, severity, confidence, summary, recommendations, gaps, cited_evidence_ids, hypotheses。"
            "cited_evidence_ids 为 evidence_items_index 中你实际引用的 id 列表（整数），不得编造未出现的 id。"
            " hypotheses 是根因假设树，列表形式，含 2-4 个候选；证据严重不足时可只给 1 个 unknown 候选。"
            "每个候选含 id (h1, h2, ...), cause, confidence (0..1),"
            " supporting_evidence_ids 与 contradicting_evidence_ids（均为 evidence_items_index 中出现过的整数 id，不得编造），"
            " 以及 next_probe（建议补采的下一步证据，自然语言，可为 null）。优先输出对主候选有反证或可证伪的候选。"
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
        # 每次执行时刷新一次激活模型，避免 settings 页面切换后 agent 仍持有旧客户端。
        self.llm_client = build_client()
        topology = context.runtime.get("topology") or {}
        device = context.runtime.get("device") or {}
        ssh_result = context.runtime.get("ssh_result") or {}
        log_summary = context.runtime.get("log_summary") or {}
        zabbix_alerts = context.runtime.get("zabbix_alerts") or {}
        ssh_available = bool(ssh_result and not ssh_result.get("skipped"))

        evidence_refs: List[Dict[str, str]] = []
        if device:
            evidence_refs.append({"type": "topology_device", "ref": "runtime.device"})
        if topology:
            evidence_refs.append({"type": "topology", "ref": "runtime.topology"})
        if log_summary:
            evidence_refs.append({"type": "log_summary", "ref": "runtime.log_summary"})
        if zabbix_alerts:
            evidence_refs.append({"type": "zabbix_alerts", "ref": "runtime.zabbix_alerts"})
        if ssh_available:
            evidence_refs.append({"type": "execution_channel", "ref": "runtime.ssh_result"})

        evidence_index = [
            {"id": item.get("id"), "evidence_type": item.get("evidence_type"), "summary": item.get("summary")}
            for item in (context.evidence_items or [])[:12]
        ]
        payload = {
            "case": {
                "title": context.title,
                "summary": context.summary,
                "source_system": context.source_system,
                "device_ip": context.device_ip,
                "host": context.host,
            },
            "insight_round": context.insight_round,
            "evidence_items_index": evidence_index,
            "log_summary": log_summary,
            "device": device,
            "topology": topology,
            "zabbix_alerts": zabbix_alerts,
            "execution_channel": ssh_result if ssh_available else {},
            "prior_claims": context.prior_claims,
        }
        llm_result = await self._infer_with_llm(payload)

        gaps = list(llm_result.get("gaps") or [])
        if not topology:
            gaps.append("缺少拓扑上下文")
        if not zabbix_alerts and context.source_system.lower() == "zabbix":
            gaps.append("缺少 Zabbix 告警详情")

        valid_ids = {int(i.get("id")) for i in (context.evidence_items or []) if i.get("id") is not None}

        # Phase 4: parse hypothesis tree from the LLM output (or synthesize from legacy fields).
        hypotheses = self._parse_hypothesis_tree(llm_result, valid_ids)
        top_hypothesis = hypotheses[0] if hypotheses else None

        cited_ids: List[int] = []
        if top_hypothesis:
            cited_ids = list(top_hypothesis.get("supporting_evidence_ids") or [])[:8]
        if not cited_ids:
            for raw in llm_result.get("cited_evidence_ids") or []:
                try:
                    cited_ids.append(int(raw))
                except (TypeError, ValueError):
                    continue
            cited_ids = [i for i in cited_ids if i in valid_ids][:8]

        default_confidence = 0.74 if topology or zabbix_alerts else 0.42
        root_cause = (top_hypothesis or {}).get("cause") or llm_result.get("root_cause") or "unknown"
        severity = llm_result.get("severity") or "warning"
        raw_confidence = llm_result.get("confidence")
        try:
            confidence = float(raw_confidence) if raw_confidence is not None else float((top_hypothesis or {}).get("confidence") or default_confidence)
        except (TypeError, ValueError):
            confidence = float((top_hypothesis or {}).get("confidence") or default_confidence)

        if root_cause == "unknown" and log_summary.get("devices"):
            top_device = log_summary["devices"][0]
            root_cause = f"device_log_pattern:{top_device.get('device_ip')}"

        summary = llm_result.get("summary") or (
            "已完成日志、拓扑、告警证据交叉分析，但证据仍不足以给出唯一根因。"
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
                "cited_evidence_ids": cited_ids,
                "hypotheses": hypotheses,
                "insight_round": context.insight_round,
                "device_context": {
                    "name": device.get("name"),
                    "role": device.get("role"),
                    "site": device.get("site"),
                },
            },
            cited_evidence_item_ids=cited_ids,
            metadata={
                "insight_round": context.insight_round,
                "hypothesis_count": len(hypotheses),
            },
        )

    # ------------------------------------------------------------------
    # Phase 4 — hypothesis tree parsing (pure / unit-testable)
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_evidence_ids(raw: Any, valid_ids: Set[int]) -> List[int]:
        """Return only valid integer evidence ids that appear in valid_ids."""
        out: List[int] = []
        if isinstance(raw, (list, tuple, set)):
            iterable: Iterable[Any] = raw
        else:
            return out
        for item in iterable:
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value in valid_ids:
                out.append(value)
        # dedupe while preserving order
        seen: Set[int] = set()
        deduped: List[int] = []
        for v in out:
            if v not in seen:
                deduped.append(v)
                seen.add(v)
        return deduped

    def _parse_hypothesis_tree(
        self,
        llm_result: Dict[str, Any],
        valid_evidence_ids: Set[int],
    ) -> List[Dict[str, Any]]:
        """
        Parse llm_result['hypotheses'] into a sanitized list.

        - Invalid / non-dict entries are dropped.
        - confidence clamped to [0, 1].
        - supporting / contradicting evidence ids filtered against valid_evidence_ids.
        - When the tree is empty (LLM didn't supply one), synthesize a single
          hypothesis from legacy root_cause + confidence + cited_evidence_ids.
        - Sorted by confidence desc.
        """
        raw_hypotheses = llm_result.get("hypotheses")
        parsed: List[Dict[str, Any]] = []
        if isinstance(raw_hypotheses, list):
            for idx, item in enumerate(raw_hypotheses):
                if not isinstance(item, dict):
                    continue
                cause = str(item.get("cause") or "").strip()
                if not cause:
                    continue
                try:
                    confidence = float(item.get("confidence") or 0.0)
                except (TypeError, ValueError):
                    confidence = 0.0
                confidence = max(0.0, min(1.0, confidence))
                supporting = self._coerce_evidence_ids(item.get("supporting_evidence_ids"), valid_evidence_ids)
                contradicting = self._coerce_evidence_ids(item.get("contradicting_evidence_ids"), valid_evidence_ids)
                next_probe = item.get("next_probe")
                if next_probe is not None and not isinstance(next_probe, str):
                    next_probe = str(next_probe)
                parsed.append({
                    "id": str(item.get("id") or f"h{idx + 1}"),
                    "cause": cause,
                    "confidence": confidence,
                    "supporting_evidence_ids": supporting,
                    "contradicting_evidence_ids": contradicting,
                    "next_probe": next_probe,
                })

        if not parsed:
            # Backward-compat fallback: synthesize from legacy fields.
            cause = str(llm_result.get("root_cause") or "unknown").strip() or "unknown"
            try:
                legacy_conf = float(llm_result.get("confidence") or 0.4)
            except (TypeError, ValueError):
                legacy_conf = 0.4
            legacy_conf = max(0.0, min(1.0, legacy_conf))
            supporting = self._coerce_evidence_ids(llm_result.get("cited_evidence_ids"), valid_evidence_ids)
            parsed = [{
                "id": "h1",
                "cause": cause,
                "confidence": legacy_conf,
                "supporting_evidence_ids": supporting,
                "contradicting_evidence_ids": [],
                "next_probe": None,
            }]

        parsed.sort(key=lambda h: -h.get("confidence", 0.0))
        return parsed


insight_analysis_agent = InsightAnalysisAgent()
