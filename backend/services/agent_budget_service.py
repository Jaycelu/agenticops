from __future__ import annotations

from sqlalchemy.orm import Session

from models.agent_graph import AgentBudget
from observability.metrics import metrics_registry


class BudgetExhausted(RuntimeError):
    pass


LIMITS = {
    "agent_runs": ("used_agent_runs", "max_agent_runs"),
    "llm_calls": ("used_llm_calls", "max_llm_calls"),
    "tool_calls": ("used_tool_calls", "max_tool_calls"),
    "probe_calls": ("used_probe_calls", "max_probe_calls"),
    "replan_count": ("used_replan_count", "max_replan_count"),
}


class AgentBudgetService:
    def consume(self, db: Session, graph_run_id: str, resource: str, amount: int = 1) -> AgentBudget:
        if resource not in LIMITS or amount < 1:
            raise ValueError("invalid budget resource")
        budget = db.query(AgentBudget).filter(AgentBudget.graph_run_id == graph_run_id).with_for_update().one()
        used_name, max_name = LIMITS[resource]
        if getattr(budget, used_name) + amount > getattr(budget, max_name):
            budget.exhausted = True
            budget.exhausted_reason = resource
            metrics_registry.increment("agent_budget_exhausted_total", resource=resource)
            db.flush()
            raise BudgetExhausted(resource)
        setattr(budget, used_name, getattr(budget, used_name) + amount)
        db.flush()
        return budget

    def record_runtime(self, db: Session, graph_run_id: str, elapsed_seconds: float) -> AgentBudget:
        budget = db.query(AgentBudget).filter(AgentBudget.graph_run_id == graph_run_id).with_for_update().one()
        budget.used_runtime_seconds = max(float(budget.used_runtime_seconds or 0), float(elapsed_seconds))
        if budget.used_runtime_seconds > budget.max_runtime_seconds:
            budget.exhausted = True
            budget.exhausted_reason = "runtime_seconds"
            metrics_registry.increment("agent_budget_exhausted_total", resource="runtime_seconds")
            db.flush()
            raise BudgetExhausted("runtime_seconds")
        db.flush()
        return budget

    def register_target(self, db: Session, graph_run_id: str, netbox_device_id: int) -> AgentBudget:
        budget = db.query(AgentBudget).filter(AgentBudget.graph_run_id == graph_run_id).with_for_update().one()
        targets = [int(item) for item in (budget.target_device_ids or [])]
        if netbox_device_id not in targets:
            if len(targets) >= budget.max_target_devices:
                budget.exhausted = True
                budget.exhausted_reason = "target_devices"
                metrics_registry.increment("agent_budget_exhausted_total", resource="target_devices")
                db.flush()
                raise BudgetExhausted("target_devices")
            targets.append(netbox_device_id)
            budget.target_device_ids = targets
        db.flush()
        return budget


agent_budget_service = AgentBudgetService()
