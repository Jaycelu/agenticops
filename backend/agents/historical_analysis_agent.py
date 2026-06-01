from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from models.agenticops import AgentType


class HistoricalAnalysisAgent(BaseOpsAgent):
    agent_type = AgentType.HISTORICAL
    agent_name = "Historical Analysis Agent"

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        memory_hits = context.memory_hits or []
        similar_cases = (context.runtime or {}).get("similar_cases") or []
        evidence_refs = [{"type": "memory", "ref": str(item.get("id"))} for item in memory_hits[:5]]
        for sc in similar_cases[:5]:
            cid = sc.get("case_id")
            if cid:
                evidence_refs.append({"type": "similar_case", "ref": f"case:{cid}"})
        gaps = []
        if not memory_hits:
            gaps.append("暂无命中的历史记忆，需要依赖实时证据判断")
        if not similar_cases:
            gaps.append("未找到同站点/设备的已关闭相似 Case")
        if not memory_hits and not similar_cases:
            summary = "未命中高相关历史记忆与相似已关单 Case，建议继续依赖实时日志与拓扑证据完成诊断。"
            confidence = 0.35
        elif memory_hits:
            best = memory_hits[0]
            summary = f"命中 {len(memory_hits)} 条历史记忆，最相关为 {best.get('title')}。"
            if similar_cases:
                summary += f" 另检索到 {len(similar_cases)} 条相似已关单 Case。"
            confidence = min(0.9, float(best.get("confidence") or 0.6))
        else:
            summary = f"检索到 {len(similar_cases)} 条相似已关单 Case，可作为处置参考。"
            confidence = 0.55

        cited_memory_ids = [int(m["id"]) for m in memory_hits[:5] if m.get("id") is not None]
        cited_case_ids = [int(s["case_id"]) for s in similar_cases[:5] if s.get("case_id") is not None]

        return AgentDecision(
            summary=summary,
            confidence=confidence,
            claim_type="historical_similarity",
            claim_text=summary,
            status="supported" if (memory_hits or similar_cases) else "hypothesis",
            evidence_refs=evidence_refs,
            gaps=gaps,
            output_payload={
                "matched_memories": memory_hits[:5],
                "match_count": len(memory_hits),
                "similar_cases": similar_cases[:5],
                "similar_case_ids": cited_case_ids,
                "memory_entry_ids": cited_memory_ids,
            },
            metadata={"memory_entry_ids": cited_memory_ids, "similar_case_ids": cited_case_ids},
        )


historical_analysis_agent = HistoricalAnalysisAgent()

