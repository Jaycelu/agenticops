from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from models.agenticops import AgentType


class HistoricalAnalysisAgent(BaseOpsAgent):
    agent_type = AgentType.HISTORICAL
    agent_name = "Historical Analysis Agent"

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        memory_hits = context.memory_hits or []
        evidence_refs = [{"type": "memory", "ref": str(item.get("id"))} for item in memory_hits[:5]]
        gaps = []
        if not memory_hits:
            gaps.append("暂无命中的历史记忆，需要依赖实时证据判断")
            summary = "未命中高相关历史案例，建议继续依赖实时日志、拓扑和 SSH 证据完成诊断。"
            confidence = 0.35
        else:
            best = memory_hits[0]
            summary = f"命中 {len(memory_hits)} 条历史记忆，最相关案例为 {best.get('title')}。"
            confidence = min(0.9, float(best.get("confidence") or 0.6))

        return AgentDecision(
            summary=summary,
            confidence=confidence,
            claim_type="historical_similarity",
            claim_text=summary,
            status="supported" if memory_hits else "hypothesis",
            evidence_refs=evidence_refs,
            gaps=gaps,
            output_payload={
                "matched_memories": memory_hits[:5],
                "match_count": len(memory_hits),
            },
        )


historical_analysis_agent = HistoricalAnalysisAgent()

