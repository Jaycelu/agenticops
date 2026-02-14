from typing import List, Optional
from pydantic import BaseModel, Field


class CommandTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    template_type: str = Field(default="diagnosis_default", min_length=1, max_length=80)
    vendor: str = Field(..., min_length=1, max_length=120)
    commands: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class CommandTemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    template_type: Optional[str] = Field(default=None, min_length=1, max_length=80)
    vendor: Optional[str] = Field(default=None, min_length=1, max_length=120)
    commands: Optional[List[str]] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class CommandTemplateValidateRequest(BaseModel):
    template_id: int
    device_ids: List[int] = Field(default_factory=list)


class CommandTemplateResolveRequest(BaseModel):
    device_id: int
    template_type: str = Field(default="diagnosis_default")
