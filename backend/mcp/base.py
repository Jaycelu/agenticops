from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class MCPResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseMCP(ABC):
    name: str = "base"
    description: str = "Base MCP class"

    def __init__(self):
        self.name = self.__class__.name

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> MCPResult:
        pass

    def _success(self, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> MCPResult:
        return MCPResult(success=True, data=data, metadata=metadata)

    def _error(self, error: str) -> MCPResult:
        return MCPResult(success=False, error=error)