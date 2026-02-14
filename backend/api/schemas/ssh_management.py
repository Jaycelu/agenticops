from typing import List, Optional
from pydantic import BaseModel, Field


class SSHCredentialCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    username: str = Field(..., min_length=1, max_length=120)
    auth_type: str = Field(default="password", pattern="^(password|private_key)$")
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    port: int = Field(default=22, ge=1, le=65535)


class SSHCredentialUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    username: Optional[str] = Field(default=None, min_length=1, max_length=120)
    auth_type: Optional[str] = Field(default=None, pattern="^(password|private_key)$")
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    enabled: Optional[bool] = None


class DeviceBindingRequest(BaseModel):
    netbox_device_ids: List[int] = Field(default_factory=list)


class NetBoxDeviceQueryRequest(BaseModel):
    site: Optional[str] = None
    tag: Optional[str] = None


class ConnectivityTestRequest(BaseModel):
    credential_id: int
    netbox_device_id: int


class ExecuteCommandRequest(BaseModel):
    credential_id: int
    netbox_device_id: int
    commands: List[str]
    timeout: int = Field(default=20, ge=3, le=120)
