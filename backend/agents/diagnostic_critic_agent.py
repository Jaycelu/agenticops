from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from models.agenticops import AgentType


class DiagnosticCriticAgent(BaseOpsAgent):
    """Deterministic falsification pass over persisted hypothesis candidates."""

    agent_type = AgentType.INSIGHT
    agent_name = "Diagnostic Critic Agent"

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        hypotheses = list(context.runtime.get("hypotheses") or [])
        evidence_by_id = {int(item["id"]): item for item in context.evidence_items if item.get("id") is not None}
        findings: list[dict[str, Any]] = []
        cited: set[int] = set()
        decision = "accept"
        for hypothesis in hypotheses:
            supporting = [int(item) for item in hypothesis.get("supporting_evidence_ids") or [] if int(item) in evidence_by_id]
            contradicting = [int(item) for item in hypothesis.get("contradicting_evidence_ids") or [] if int(item) in evidence_by_id]
            cited.update(supporting)
            cited.update(contradicting)
            sources = {str(evidence_by_id[item].get("source_system") or "unknown") for item in supporting}
            stale = []
            for item in supporting:
                collected = evidence_by_id[item].get("collected_at")
                if collected and getattr(collected, "tzinfo", None) is None:
                    collected = collected.replace(tzinfo=timezone.utc)
                if collected and (datetime.now(timezone.utc) - collected).total_seconds() > 3600:
                    stale.append(item)
            if contradicting:
                findings.append({"code": "contradiction", "hypothesis": hypothesis.get("hypothesis_code"), "evidence_ids": contradicting})
                decision = "revise"
            if len(sources) < 2 and not any(evidence_by_id[item].get("evidence_type") == "command_output" for item in supporting):
                findings.append({"code": "single_source", "hypothesis": hypothesis.get("hypothesis_code"), "evidence_ids": supporting})
                decision = "revise"
            if stale:
                findings.append({"code": "stale_evidence", "hypothesis": hypothesis.get("hypothesis_code"), "evidence_ids": stale})
                decision = "reject"
        if not hypotheses:
            decision = "reject"
            findings.append({"code": "no_hypothesis", "evidence_ids": []})
        summary = f"Diagnostic Critic: {decision}; findings={len(findings)}"
        return AgentDecision(
            summary=summary,
            confidence=0.9,
            claim_type="diagnostic_critique",
            claim_text=summary,
            status="rejected" if decision == "reject" else ("hypothesis" if decision == "revise" else "supported"),
            evidence_refs=[{"type": "evidence", "ref": str(item)} for item in sorted(cited)],
            gaps=[item["code"] for item in findings],
            output_payload={"decision": decision, "findings": findings, "cited_evidence_ids": sorted(cited)},
            cited_evidence_item_ids=sorted(cited),
        )


diagnostic_critic_agent = DiagnosticCriticAgent()
