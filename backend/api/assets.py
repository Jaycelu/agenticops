from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from mcp.netbox_mcp import NetBoxMCP
from utils.cache import netbox_cache
from database import get_db
from services.asset_sync_service import asset_sync_service
from models.automation import AssetDevice
from api.schemas.common import MessageResponse, error_detail
from api.schemas.assets import (
    DeviceListResponse,
    IPListResponse,
    SiteListResponse,
    RackListResponse,
    VLANListResponse,
    PrefixListResponse,
    VendorsResponse,
    SyncDevicesResponse,
    FetchConfigRequest,
)
from auth.dependencies import require_permissions
from auth.rbac import Permission

router = APIRouter(prefix="/api/assets", tags=["assets"])
netbox_mcp = NetBoxMCP()


@router.get("/devices", response_model=DeviceListResponse)
async def get_devices(
    name: str = None,
    site: str = None,
    role: str = None,
    vendor: str = None,
    db: Session = Depends(get_db),
):
    params = {"action": "query_devices"}
    if name:
        params["name"] = name
    if site:
        params["site"] = site
    if role:
        params["role"] = role
    if vendor:
        params["vendor"] = vendor

    # 尝试从缓存获取
    cached_data = netbox_cache.get("devices", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        devices = result.data.get("devices", []) if isinstance(result.data, dict) else []
        if devices:
            asset_sync_service.sync_devices(db, devices)
        # 缓存结果
        netbox_cache.set("devices", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/ips", response_model=IPListResponse)
async def get_ips(address: str = None, device_id: int = None, status: str = None):
    params = {"action": "query_ips"}
    if address:
        params["address"] = address
    if device_id:
        params["device_id"] = device_id
    if status:
        params["status"] = status

    # 尝试从缓存获取
    cached_data = netbox_cache.get("ips", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 缓存结果
        netbox_cache.set("ips", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/sites", response_model=SiteListResponse)
async def get_sites():
    params = {"action": "query_sites"}

    # 尝试从缓存获取
    cached_data = netbox_cache.get("sites", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 缓存结果
        netbox_cache.set("sites", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/racks", response_model=RackListResponse)
async def get_racks(name: str = None, site: str = None, status: str = None):
    params = {"action": "query_racks"}
    if name:
        params["name"] = name
    if site:
        params["site"] = site
    if status:
        params["status"] = status

    # 尝试从缓存获取
    cached_data = netbox_cache.get("racks", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 缓存结果
        netbox_cache.set("racks", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/racks/{rack_id:int}/devices", response_model=DeviceListResponse)
async def get_rack_devices(rack_id: int):
    """获取指定机柜内的设备"""
    params = {"action": "query_devices", "rack_id": rack_id}

    # 尝试从缓存获取
    cached_data = netbox_cache.get("rack_devices", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 缓存结果
        netbox_cache.set("rack_devices", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.post(
    "/clear-cache",
    response_model=MessageResponse,
    dependencies=[Depends(require_permissions(Permission.INTEGRATIONS_MANAGE.value))],
)
async def clear_cache():
    """清除资产缓存"""
    for prefix in [
        "devices",
        "ips",
        "sites",
        "racks",
        "rack_devices",
        "vlans",
        "prefixes",
        "prefix_ips",
        "devices_with_ip",
    ]:
        netbox_cache.clear(prefix)
    return {"message": "Cache cleared successfully"}


@router.get("/vlans", response_model=VLANListResponse)
async def get_vlans(name: str = None, site: str = None, vid: int = None, status: str = None):
    params = {"action": "query_vlans"}
    if name:
        params["name"] = name
    if site:
        params["site"] = site
    if vid:
        params["vid"] = vid
    if status:
        params["status"] = status

    # 尝试从缓存获取
    cached_data = netbox_cache.get("vlans", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 缓存结果
        netbox_cache.set("vlans", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/prefixes", response_model=PrefixListResponse)
async def get_prefixes(prefix: str = None, site: str = None, family: int = None, status: str = None):
    params = {"action": "query_prefixes"}
    if prefix:
        params["prefix"] = prefix
    if site:
        params["site"] = site
    if family:
        params["family"] = family
    if status:
        params["status"] = status

    # 尝试从缓存获取
    cached_data = netbox_cache.get("prefixes", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 缓存结果
        netbox_cache.set("prefixes", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/prefixes/{prefix_id:int}/ips", response_model=IPListResponse)
async def get_prefix_ips(prefix_id: int):
    """获取指定前缀内的IP地址"""
    params = {"action": "query_ips", "parent_prefix_id": prefix_id}

    # 尝试从缓存获取
    cached_data = netbox_cache.get("prefix_ips", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 获取前缀信息以计算利用率
        prefix_params = {"action": "query_prefixes", "prefix_id": prefix_id}
        prefix_result = await netbox_mcp.execute(prefix_params)
        
        if prefix_result.success and prefix_result.data.get("prefixes"):
            prefix_data = prefix_result.data["prefixes"][0]
            result.data["utilization"] = prefix_data.get("utilization", 0)
            result.data["total_ips"] = prefix_data.get("total_ips", 0)
            result.data["used_ips"] = prefix_data.get("used_ips", 0)
        
        # 缓存结果
        netbox_cache.set("prefix_ips", params, result.data)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/devices/{device_id:int}/config")
async def get_device_config(device_id: int):
    """获取指定设备的配置信息"""
    params = {"action": "get_device_config", "device_id": device_id}

    # 设备配置不缓存，实时获取
    result = await netbox_mcp.execute(params)
    if result.success:
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/devices/with-ip", response_model=DeviceListResponse)
async def get_devices_with_ip(
    site: str = None,
    role: str = None,
    status: str = None,
    vendor: str = None,
    db: Session = Depends(get_db),
):
    """获取有IP地址的设备（用于自动化模块选择）"""
    params = {"action": "query_devices"}

    if site:
        params["site"] = site
    if role:
        params["role"] = role
    if status:
        params["status"] = status
    if vendor:
        params["vendor"] = vendor

    # 尝试从缓存获取
    cached_data = netbox_cache.get("devices_with_ip", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求NetBox
    result = await netbox_mcp.execute(params)
    if result.success:
        # 过滤出有IP的设备
        devices_with_ip = [
            device for device in result.data.get("devices", [])
            if device.get("primary_ip")
        ]
        if devices_with_ip:
            asset_sync_service.sync_devices(db, devices_with_ip)

        filtered_result = {
            "count": len(devices_with_ip),
            "devices": devices_with_ip
        }

        # 缓存结果
        netbox_cache.set("devices_with_ip", params, filtered_result)
        return filtered_result
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.get("/devices/{device_id:int}")
async def get_device_detail(device_id: int, db: Session = Depends(get_db)):
    params = {"action": "get_device_by_id", "device_id": device_id}
    result = await netbox_mcp.execute(params)
    if not result.success:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))

    data = result.data or {}
    vendor = data.get("manufacturer") or data.get("vendor")
    # 更新本地镜像
    payload = {
        "id": data.get("id"),
        "name": data.get("name"),
        "device_type": data.get("device_type"),
        "site": data.get("site"),
        "role": data.get("role"),
        "vendor": vendor,
        "manufacturer": vendor,
        "status": data.get("status"),
        "serial": data.get("serial"),
        "primary_ip": data.get("primary_ip"),
        "rack": data.get("rack"),
        "position": data.get("position"),
        "face": data.get("face"),
        "tags": data.get("tags", []),
    }
    asset_sync_service.sync_devices(db, [payload])
    data["vendor"] = vendor
    return data


@router.post(
    "/devices/{device_id:int}/fetch-config",
    dependencies=[Depends(require_permissions(Permission.CREDENTIALS_MANAGE.value))],
)
async def fetch_and_save_device_config(device_id: int, credentials: FetchConfigRequest):
    """从设备获取配置并写入NetBox"""
    params = {
        "action": "fetch_and_save_device_config",
        "device_id": device_id,
        "username": credentials.username,
        "password": credentials.password,
        "port": credentials.port,
        "enable_password": credentials.enable_password
    }

    result = await netbox_mcp.execute(params)
    if result.success:
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))


@router.post(
    "/sync/devices",
    response_model=SyncDevicesResponse,
    dependencies=[Depends(require_permissions(Permission.INTEGRATIONS_MANAGE.value))],
)
async def sync_devices(site: str = None, vendor: str = None, db: Session = Depends(get_db)):
    params = {"action": "query_devices"}
    if site:
        params["site"] = site
    if vendor:
        params["vendor"] = vendor
    result = await netbox_mcp.execute(params)
    if not result.success:
        raise HTTPException(status_code=500, detail=error_detail("ASSET_UPSTREAM_ERROR", result.error))
    devices = result.data.get("devices", []) if isinstance(result.data, dict) else []
    summary = asset_sync_service.sync_devices(db, devices)
    return {"success": True, "data": summary}


@router.get("/vendors", response_model=VendorsResponse)
async def list_vendors(db: Session = Depends(get_db)):
    vendors = db.query(AssetDevice.vendor).filter(
        AssetDevice.vendor.isnot(None),
        AssetDevice.vendor != ""
    ).distinct().order_by(AssetDevice.vendor.asc()).all()
    return {"success": True, "data": [v[0] for v in vendors]}
