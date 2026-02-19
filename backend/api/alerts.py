import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.automation import AlertEvent
from mcp.zabbix_mcp import ZabbixMCP
from utils.cache import netbox_cache
from api.schemas.common import MessageResponse, PageMeta, error_detail
from api.schemas.alerts import (
    AcknowledgeRequest,
    AcknowledgeResponse,
    AlertEventCreateRequest,
    AlertEventItem,
    AlertEventListResponse,
    AlertListResponse,
    AlertStatisticsResponse,
    HostListResponse,
    ProblemListResponse,
    TriggerListResponse,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
zabbix_mcp = ZabbixMCP()


def _parse_clock(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value))
    except Exception:
        return None


def _build_dedup_key(payload: AlertEventCreateRequest) -> str:
    source_key = payload.source or "UNKNOWN"
    event_key = payload.external_event_id or f"{payload.host}|{payload.name}|{payload.severity_level}"
    return hashlib.md5(f"{source_key}|{event_key}".encode()).hexdigest()


def _upsert_alert_event(db: Session, payload: AlertEventCreateRequest) -> AlertEvent:
    dedup_key = payload.dedup_key or _build_dedup_key(payload)
    record = db.query(AlertEvent).filter(AlertEvent.dedup_key == dedup_key).first()
    if not record:
        record = AlertEvent(dedup_key=dedup_key)
        db.add(record)

    record.source = payload.source
    record.external_event_id = payload.external_event_id
    record.site_id = payload.site_id
    record.netbox_device_id = payload.netbox_device_id
    record.host = payload.host
    record.name = payload.name
    record.severity = payload.severity
    record.severity_level = payload.severity_level
    record.status = "open"
    record.acknowledged = False
    record.occurred_at = payload.occurred_at or datetime.now()
    record.last_seen_at = datetime.now()
    record.payload = payload.payload
    return record


@router.get("/alerts", response_model=AlertListResponse)
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
        raise HTTPException(status_code=500, detail=error_detail("ALERT_UPSTREAM_ERROR", result.error))


@router.get("/problems", response_model=ProblemListResponse)
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
        raise HTTPException(status_code=500, detail=error_detail("ALERT_UPSTREAM_ERROR", result.error))


@router.get("/hosts", response_model=HostListResponse)
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
        raise HTTPException(status_code=500, detail=error_detail("ALERT_UPSTREAM_ERROR", result.error))


@router.get("/triggers", response_model=TriggerListResponse)
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
        raise HTTPException(status_code=500, detail=error_detail("ALERT_UPSTREAM_ERROR", result.error))


@router.get("/statistics", response_model=AlertStatisticsResponse)
async def get_statistics():
    """获取告警统计信息"""
    # 获取当前告警统计
    alert_params = {"action": "query_alerts", "limit": 2000}
    alert_result = await zabbix_mcp.execute(alert_params)

    if not alert_result.success:
        raise HTTPException(status_code=500, detail=error_detail("ALERT_UPSTREAM_ERROR", alert_result.error))

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


@router.post("/acknowledge", response_model=AcknowledgeResponse)
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
        for prefix in ["alerts", "problems", "hosts", "triggers"]:
            netbox_cache.clear(prefix)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("ALERT_UPSTREAM_ERROR", result.error))


@router.post("/clear-cache", response_model=MessageResponse)
async def clear_cache():
    """清除告警缓存"""
    for prefix in ["alerts", "problems", "hosts", "triggers"]:
        netbox_cache.clear(prefix)
    return {"message": "Cache cleared successfully"}


@router.post("/events", response_model=AlertEventItem)
async def create_alert_event(payload: AlertEventCreateRequest, db: Session = Depends(get_db)):
    """告警事件入库（自动化中心消费入口）"""
    record = _upsert_alert_event(db, payload)
    db.commit()
    db.refresh(record)
    return record


@router.get("/events", response_model=AlertEventListResponse)
async def list_alert_events(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    site_id: Optional[int] = None,
    netbox_device_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(AlertEvent)
    if status:
        query = query.filter(AlertEvent.status == status)
    if severity:
        query = query.filter(AlertEvent.severity == severity)
    if source:
        query = query.filter(AlertEvent.source == source)
    if site_id is not None:
        query = query.filter(AlertEvent.site_id == site_id)
    if netbox_device_id is not None:
        query = query.filter(AlertEvent.netbox_device_id == netbox_device_id)

    total = query.count()
    records = query.order_by(AlertEvent.occurred_at.desc()).offset(skip).limit(limit).all()
    returned = len(records)
    return {
        "page": PageMeta(
            total=total,
            skip=skip,
            limit=limit,
            returned=returned,
            has_more=(skip + returned) < total,
        ),
        "events": records,
    }


@router.post("/events/sync-from-zabbix", response_model=MessageResponse)
async def sync_events_from_zabbix(limit: int = Query(200, ge=1, le=2000), db: Session = Depends(get_db)):
    result = await zabbix_mcp.execute({"action": "query_alerts", "limit": limit})
    if not result.success:
        raise HTTPException(status_code=500, detail=error_detail("ALERT_UPSTREAM_ERROR", result.error))

    for alert in result.data.get("alerts", []):
        payload = AlertEventCreateRequest(
            source="ZABBIX",
            external_event_id=str(alert.get("eventid")) if alert.get("eventid") is not None else None,
            host=alert.get("host"),
            name=alert.get("name") or "Zabbix Alert",
            severity=alert.get("severity") or "未分类",
            severity_level=int(alert.get("severity_level") or 0),
            occurred_at=_parse_clock(alert.get("clock")),
            payload=alert,
        )
        record = _upsert_alert_event(db, payload)
        if int(alert.get("acknowledged", 0)) == 1:
            record.acknowledged = True
            record.status = "acknowledged"
    db.commit()
    return {"message": "Synced alerts from Zabbix"}


@router.post("/events/{event_id}/acknowledge", response_model=AlertEventItem)
async def acknowledge_alert_event(event_id: int, db: Session = Depends(get_db)):
    record = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=error_detail("ALERT_EVENT_NOT_FOUND", "Alert event not found"))
    record.acknowledged = True
    record.status = "acknowledged"
    record.last_seen_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


@router.post("/events/{event_id}/resolve", response_model=AlertEventItem)
async def resolve_alert_event(event_id: int, db: Session = Depends(get_db)):
    record = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=error_detail("ALERT_EVENT_NOT_FOUND", "Alert event not found"))
    record.status = "resolved"
    record.resolved_at = datetime.now()
    record.last_seen_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record
