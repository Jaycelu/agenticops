from typing import Dict, Any, Optional
from pydantic import BaseModel


class ModelConfig(BaseModel):
    id: str
    name: str
    provider: str
    api_key: str
    api_url: str
    model: str
    is_active: bool = False
    parameters: Dict[str, Any] = {}


class ModelUpdateRequest(BaseModel):
    model_id: str
    name: Optional[str] = None
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ModelCreateRequest(BaseModel):
    name: str
    provider: str
    api_key: str
    api_url: str
    model: str
    parameters: Optional[Dict[str, Any]] = {}
