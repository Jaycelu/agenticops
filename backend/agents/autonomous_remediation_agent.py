from typing import List

from agents.base import BaseOpsAgent
from agents.schemas import AgentDecision, AgentExecutionContext
from config.settings import settings
from models.agenticops import AgentType


class AutonomousRemediationAgent(BaseOpsAgent):
    agent_type = AgentType.REMEDIATION
    agent_name = "Autonomous Remediation Agent"

    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        prior_claims = context.prior_claims or []
        insight_claim = next((item for item in prior_claims if item.get("claim_type") == "root_cause_assessment"), {})
        triage_claim = next((item for item in prior_claims if item.get("claim_type") == "triage_assessment"), {})

        root_cause = ((insight_claim.get("output_payload") or {}).get("root_cause")) or "unknown"
        priority = ((triage_claim.get("metadata") or {}).get("priority")) or "P3"
        confidence = float(insight_claim.get("confidence") or triage_claim.get("confidence") or 0.4)
        recommendations: List[str] = list(((insight_claim.get("output_payload") or {}).get("recommendations")) or [])

        if not recommendations:
            recommendations = ["保留现场，继续观察", "补充设备现场证据", "必要时人工介入复核"]

        execution_mode = "manual"
        approval_status = "required"
        if not settings.automation_observe_only and confidence >= 0.85 and priority in {"P2", "P3"}:
            execution_mode = "auto"
            approval_status = "not_required"

        summary = (
            f"已生成修复计划草案，根因候选为 {root_cause}，执行模式 {execution_mode}，"
            f"当前系统 observe_only={settings.automation_observe_only}。"
        )

        return AgentDecision(
            summary=summary,
            confidence=min(0.9, max(0.45, confidence)),
            claim_type="remediation_strategy",
            claim_text=summary,
            status="actionable",
            evidence_refs=[{"type": "claim", "ref": item.get("id", "runtime")} for item in prior_claims[-3:]],
            gaps=[],
            output_payload={
                "root_cause": root_cause,
                "execution_mode": execution_mode,
                "approval_status": approval_status,
                "recommendations": recommendations,
                "safety_checks": {
                    "observe_only": settings.automation_observe_only,
                    "requires_approval": approval_status == "required",
                    "confidence_threshold_met": confidence >= 0.85,
                },
                "rollback_plan": [
                    "记录变更前状态",
                    "若执行验证失败，回退到变更前配置",
                    "自动记录审计并转人工确认",
                ],
            },
        )


autonomous_remediation_agent = AutonomousRemediationAgent()

