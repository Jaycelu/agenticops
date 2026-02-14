from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
from mcp.zabbix_mcp import ZabbixMCP
from utils.cache import netbox_cache

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
zabbix_mcp = ZabbixMCP()


class AcknowledgeRequest(BaseModel):
    event_ids: list[str]
    message: str = "已通过NetOps平台确认"


@router.get("/alerts")
async def get_alerts(
    severity: Optional[int] = None,
    host: Optional[str] = None,
    time_from: Optional[int] = None,
    time_till: Optional[int] = None,
    acknowledged: Optional[int] = None,
    limit: int = 100
):
    """获取当前告警列表"""
    params = {"action": "query_alerts"}
    if severity is not None:
        params["severity"] = severity
    if host:
        params["host"] = host
    if time_from:
        params["time_from"] = time_from
    if time_till:
        params["time_till"] = time_till
    if acknowledged is not None:
        params["acknowledged"] = acknowledged
    params["limit"] = limit

    # 尝试从缓存获取
    cached_data = netbox_cache.get("alerts", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求Zabbix
    result = await zabbix_mcp.execute(params)
    if result.success:
        # 缓存结果（30秒）
        netbox_cache.set("alerts", params, result.data, ttl=30)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=result.error)


@router.get("/problems")
async def get_problems(
    severity: Optional[int] = None,
    host: Optional[str] = None,
    recent: Optional[str] = None,
    limit: int = 100
):
    """获取问题列表（包含已解决的问题）"""
    params = {"action": "query_problems"}
    if severity is not None:
        params["severity"] = severity
    if host:
        params["host"] = host
    if recent:
        params["recent"] = recent
    params["limit"] = limit

    # 尝试从缓存获取
    cached_data = netbox_cache.get("problems", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求Zabbix
    result = await zabbix_mcp.execute(params)
    if result.success:
        # 缓存结果（30秒）
        netbox_cache.set("problems", params, result.data, ttl=30)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=result.error)


@router.get("/hosts")
async def get_hosts(
    search: Optional[str] = None,
    limit: int = 100
):
    """获取主机列表"""
    params = {"action": "query_hosts"}
    if search:
        params["search"] = search
    params["limit"] = limit

    # 尝试从缓存获取
    cached_data = netbox_cache.get("hosts", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求Zabbix
    result = await zabbix_mcp.execute(params)
    if result.success:
        # 缓存结果（5分钟）
        netbox_cache.set("hosts", params, result.data, ttl=300)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=result.error)


@router.get("/triggers")
async def get_triggers(
    severity: Optional[int] = None,
    host: Optional[str] = None,
    limit: int = 100
):
    """获取触发器列表"""
    params = {"action": "query_triggers"}
    if severity is not None:
        params["severity"] = severity
    if host:
        params["host"] = host
    params["limit"] = limit

    # 尝试从缓存获取
    cached_data = netbox_cache.get("triggers", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求Zabbix
    result = await zabbix_mcp.execute(params)
    if result.success:
        # 缓存结果（5分钟）
        netbox_cache.set("triggers", params, result.data, ttl=300)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=result.error)


@router.get("/statistics")
async def get_statistics():
    """获取告警统计信息"""
    # 获取当前告警统计
    alert_params = {"action": "query_alerts", "limit": 2000}
    alert_result = await zabbix_mcp.execute(alert_params)
    
    if not alert_result.success:
        raise HTTPException(status_code=500, detail=alert_result.error)
    
    alerts = alert_result.data.get("alerts", [])
    
    # 按严重级别统计
    severity_stats = {}
    for alert in alerts:
        severity = alert.get("severity", "未分类")
        severity_stats[severity] = severity_stats.get(severity, 0) + 1
    
    # 统计已确认和未确认
    acknowledged = sum(1 for a in alerts if a.get("acknowledged") == 1)
    unacknowledged = len(alerts) - acknowledged
    
    # 获取主机统计
    host_params = {"action": "query_hosts", "limit": 1000}
    host_result = await zabbix_mcp.execute(host_params)
    
    hosts = []
    if host_result.success:
        hosts = host_result.data.get("hosts", [])
    
    enabled_hosts = sum(1 for h in hosts if h.get("status") == "启用")
    disabled_hosts = len(hosts) - enabled_hosts
    
    return {
        "total_alerts": len(alerts),
        "acknowledged": acknowledged,
        "unacknowledged": unacknowledged,
        "severity_stats": severity_stats,
        "total_hosts": len(hosts),
        "enabled_hosts": enabled_hosts,
        "disabled_hosts": disabled_hosts
    }


@router.post("/acknowledge")
async def acknowledge_alerts(request: AcknowledgeRequest):
    """确认告警"""
    params = {
        "action": "acknowledge",
        "event_ids": request.event_ids,
        "message": request.message
    }
    
    result = await zabbix_mcp.execute(params)
    if result.success:
        # 清除告警缓存
        netbox_cache.clear()
        return result.data
    else:
        raise HTTPException(status_code=500, detail=result.error)


@router.post("/clear-cache")
async def clear_cache():
    """清除告警缓存"""
    netbox_cache.clear()
    return {"message": "Cache cleared successfully"}