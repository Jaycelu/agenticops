from abc import ABC, abstractmethod

from agents.schemas import AgentDecision, AgentExecutionContext
from models.agenticops import AgentType


class BaseOpsAgent(ABC):
    agent_type: AgentType
    agent_name: str

    @abstractmethod
    async def run(self, context: AgentExecutionContext) -> AgentDecision:
        raise NotImplementedError

