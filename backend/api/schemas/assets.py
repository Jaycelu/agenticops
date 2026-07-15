from typing import Any, List, Optional

from pydantic import BaseModel, Field


class DeviceItem(BaseModel):
    id: int
    name: Optional[str] = None
    device_type: Optional[str] = None
    site: Optional[str] = None
    role: Optional[str] = None
    vendor: Optional[str] = None
    manufacturer: Optional[str] = None
    status: Optional[str] = None
    serial: Optional[str] = None
    primary_ip: Optional[str] = None
    rack: Optional[str] = None
    position: Optional[int] = None
    face: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class DeviceListResponse(BaseModel):
    count: int = Field(ge=0)
    devices: List[DeviceItem] = Field(default_factory=list)


class IPItem(BaseModel):
    id: int
    address: str
    description: Optional[str] = None
    status: Optional[str] = None
    assigned_object_type: Optional[str] = None
    assigned_object_id: Optional[int] = None
    dns_name: Optional[str] = None


class IPListResponse(BaseModel):
    count: int = Field(ge=0)
    ips: List[IPItem] = Field(default_factory=list)


class SiteItem(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class SiteListResponse(BaseModel):
    count: int = Field(ge=0)
    sites: List[SiteItem] = Field(default_factory=list)


class RackItem(BaseModel):
    id: int
    name: str
    site: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    u_height: Optional[int] = None
    width: Optional[int] = None
    role: Optional[str] = None
    serial: Optional[str] = None
    asset_tag: Optional[str] = None


class RackListResponse(BaseModel):
    count: int = Field(ge=0)
    racks: List[RackItem] = Field(default_factory=list)


class VLANItem(BaseModel):
    id: int
    vid: int
    name: str
    site: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    tenant: Optional[str] = None
    role: Optional[str] = None


class VLANListResponse(BaseModel):
    count: int = Field(ge=0)
    vlans: List[VLANItem] = Field(default_factory=list)


class PrefixItem(BaseModel):
    id: int
    prefix: str
    site: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    tenant: Optional[str] = None
    family: Optional[Any] = None
    vlan: Optional[str] = None
    vlan_vid: Optional[int] = None
    total_ips: Optional[int] = None
    used_ips: Optional[int] = None
    utilization: Optional[float] = None


class PrefixListResponse(BaseModel):
    count: int = Field(ge=0)
    prefixes: List[PrefixItem] = Field(default_factory=list)


class VendorsResponse(BaseModel):
    success: bool
    data: List[str] = Field(default_factory=list)


class SyncSummary(BaseModel):
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    total: int = Field(ge=0)


class SyncDevicesResponse(BaseModel):
    success: bool
    data: SyncSummary


class FetchConfigRequest(BaseModel):
    username: str
    password: str
    port: int = 22
    enable_password: Optional[str] = None
