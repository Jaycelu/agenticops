from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import hashlib
from mcp.elk_mcp import ELKMCP
from utils.cache import netbox_cache
from services.log_analyzer import LogAnalyzer
from models.llm_client import LLMClient
from database import SessionLocal
from engines.case_orchestrator import case_orchestrator
from api.schemas.common import MessageResponse, error_detail
from api.schemas.logs import BaseConfigsResponse, LogsResponse, AggregationResponse
from services.log_scope_service import log_scope_service

router = APIRouter(prefix="/api/logs", tags=["logs"])
elk_mcp = ELKMCP()
llm_client = LLMClient()
log_analyzer = LogAnalyzer(llm_client)


class LogQueryRequest(BaseModel):
    query: str = "*"
    time_range: str = "-1d,now"
    limit: int = 100
    offset: int = 0


@router.get("/bases", response_model=BaseConfigsResponse)
async def get_base_configs():
    """获取所有日志范围配置（兼容旧 bases 接口）"""
    result = await elk_mcp.execute({"action": "get_base_configs"})
    if result.success:
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("LOG_UPSTREAM_ERROR", result.error))


@router.get("/scopes", response_model=BaseConfigsResponse)
async def get_log_scopes():
    return await get_base_configs()


@router.get("/query", response_model=LogsResponse)
async def query_logs(
    query: Optional[str] = "*",
    time_range: Optional[str] = "-1d,now",
    limit: int = 100,
    offset: int = 0
):
    """查询日志数据"""
    params = {
        "action": "query_logs",
        "query": query,
        "time_range": time_range,
        "limit": limit,
        "offset": offset
    }

    # 尝试从缓存获取
    cached_data = netbox_cache.get("logs", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求ELK
    result = await elk_mcp.execute(params)
    if result.success:
        # 缓存结果（60秒）
        netbox_cache.set("logs", params, result.data, ttl=60)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("LOG_UPSTREAM_ERROR", result.error))


@router.get("/search", response_model=LogsResponse)
async def search_logs(
    base: str,
    time_range: Optional[str] = None,
    filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """搜索日志数据（用于前端）"""
    params = {
        "action": "query_logs_by_base",
        "base_name": base,
        "time_range": time_range,
        "limit": limit,
        "offset": offset
    }
    
    # 如果提供了自定义筛选条件，则使用自定义筛选条件
    if filter:
        params["custom_filter"] = filter

    # 尝试从缓存获取
    cached_data = netbox_cache.get(f"logs_{base}", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求ELK
    result = await elk_mcp.execute(params)
    if result.success:
        # 缓存结果（60秒）
        netbox_cache.set(f"logs_{base}", params, result.data, ttl=60)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("LOG_UPSTREAM_ERROR", result.error))


@router.get("/base/{base_name}", response_model=LogsResponse)
async def query_logs_by_base(
    base_name: str,
    time_range: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    filter: Optional[str] = None
):
    """按基地查询日志数据"""
    params = {
        "action": "query_logs_by_base",
        "base_name": base_name,
        "time_range": time_range,
        "limit": limit,
        "offset": offset
    }
    
    # 如果提供了自定义筛选条件，则使用自定义筛选条件
    if filter:
        params["custom_filter"] = filter

    # 尝试从缓存获取
    cached_data = netbox_cache.get(f"logs_{base_name}", params)
    if cached_data is not None:
        return cached_data

    # 缓存未命中，请求ELK
    result = await elk_mcp.execute(params)
    if result.success:
        # 缓存结果（60秒）
        netbox_cache.set(f"logs_{base_name}", params, result.data, ttl=60)
        return result.data
    else:
        raise HTTPException(status_code=500, detail=error_detail("LOG_UPSTREAM_ERROR", result.error))


@router.post("/clear-cache", response_model=MessageResponse)
async def clear_cache():
    """清除日志缓存"""
    netbox_cache.clear("logs")
    db = SessionLocal()
    try:
        for scope in log_scope_service.list_scopes(db, enabled_only=True):
            netbox_cache.clear(f"logs_{scope['scope_key']}")
    finally:
        db.close()
    return {"message": "Cache cleared successfully"}


class SingleLogAnalysisRequest(BaseModel):
    message: str
    hostname: Optional[str] = None


@router.post("/analyze-single")
async def analyze_single_log(request: SingleLogAnalysisRequest):
    """使用 AI 分析单条日志"""
    try:
        import re
        
        # 使用传入的 hostname，如果未提供则从消息中提取
        hostname = request.hostname if request.hostname else "Unknown"
        device_ip = "Unknown"
        raw_message = request.message
        
        # 如果 hostname 是 "Unknown"，尝试从日志消息中提取
        if hostname == "Unknown":
            hostname_match = re.search(r'[A-Z]{2,4}-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+', raw_message)
            if hostname_match:
                hostname = hostname_match.group(0)
        
        # 检查 hostname 是否是 IP 地址格式
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
            device_ip = hostname
        else:
            # 提取IP地址 (从 DevIP= 或直接出现)
            devip_match = re.search(r'DevIP=(\d+\.\d+\.\d+\.\d+)', raw_message)
            if devip_match:
                device_ip = devip_match.group(1)
            else:
                # 尝试直接提取IP地址
                ip_match = re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', raw_message)
                if ip_match:
                    device_ip = ip_match.group(0)
        
        # 构造单条日志数据
        log_entry = {
            "message": raw_message,
            "raw": {"raw_message": raw_message},
            "timestamp": "",
            "hostname": hostname,
            "device_ip": device_ip
        }

        # 使用 LLM 分析日志
        analysis_result = await log_analyzer.analyze_logs(
            logs=[log_entry],
            base_name="unknown",
            base_name_cn="未知"
        )

        if not analysis_result.get("success"):
            raise HTTPException(status_code=500, detail=analysis_result.get("error"))

        return {
            "success": True,
            "analysis": analysis_result.get("result", ""),
            "log_count": 1,
            "device_info": {
                "hostname": hostname,
                "device_ip": device_ip
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"单条日志分析失败：{str(e)}")


class LogAnalysisRequest(BaseModel):
    base_name: str
    base_name_cn: Optional[str] = ""
    time_range: Optional[str] = None
    limit: int = 100
    logs: Optional[List[Dict[str, Any]]] = None


@router.post("/analyze")
async def analyze_logs(request: LogAnalysisRequest):
    """使用 AI 分析日志数据"""
    try:
        # 如果请求中包含 logs 数据，直接使用
        if hasattr(request, 'logs') and request.logs:
            logs = request.logs
            base_name_cn = request.base_name_cn
        else:
            # 否则从 ELK 获取日志数据
            params = {
                "action": "query_logs_by_base",
                "base_name": request.base_name,
                "time_range": request.time_range,
                "limit": request.limit,
                "offset": 0
            }

            result = await elk_mcp.execute(params)
            if not result.success:
                raise HTTPException(status_code=500, detail=result.error)

            logs = result.data.get("logs", [])
            base_name_cn = request.base_name_cn or result.data.get("base_name_cn", "")

        if not logs:
            # 返回无日志的分析结果
            no_logs_result = await log_analyzer.analyze_logs(
                logs=[],
                base_name=request.base_name,
                base_name_cn=base_name_cn
            )
            return no_logs_result

        # 使用 LLM 分析日志
        analysis_result = await log_analyzer.analyze_logs(
            logs=logs,
            base_name=request.base_name,
            base_name_cn=base_name_cn
        )

        if not analysis_result.get("success"):
            raise HTTPException(status_code=500, detail=analysis_result.get("error"))

        return analysis_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"日志分析失败：{str(e)}")


class LogAggregationRequest(BaseModel):
    base_name: str
    time_range: Optional[str] = "-1d,now"
    filter: Optional[str] = None
    create_case: bool = False
    run_pipeline: bool = False
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    device_ip: Optional[str] = None
    host: Optional[str] = None
    title: Optional[str] = None
    aggregation: Dict[str, Any] = {
        "by_device": True,
        "by_level": True,
        "by_time_window": "5m"
    }


@router.post("/aggregate", response_model=AggregationResponse)
async def aggregate_logs(request: LogAggregationRequest):
    """聚合日志数据"""
    try:
        # 分批获取所有日志数据
                all_logs = []
                batch_size = 1000
                offset = 0
                has_more = True
                max_batches = 50  # 最多获取50批，避免无限循环
                actual_total = 0  # 记录实际的总数
                batch_count = 0
                
                while has_more and len(all_logs) < 100000 and max_batches > 0:  # 最多获取10万条日志
                    params = {
                        "action": "query_logs_by_base",
                        "base_name": request.base_name,
                        "time_range": request.time_range,
                        "limit": batch_size,
                        "offset": offset
                    }
                    
                    if request.filter:
                        params["custom_filter"] = request.filter
        
                    result = await elk_mcp.execute(params)
                    if not result.success:
                        raise HTTPException(status_code=500, detail=error_detail("LOG_UPSTREAM_ERROR", result.error))
        
                    batch_logs = result.data.get("logs", [])
                    all_logs.extend(batch_logs)
                    batch_count += 1
                    
                    # 记录第一次查询返回的总数
                    if offset == 0:
                        actual_total = result.data.get("total", 0)
                    
                    # 检查是否还有更多数据
                    # 如果实际获取的数量已经超过总数，或者获取的数量少于批次大小，则停止
                    has_more = len(all_logs) < actual_total and len(batch_logs) == batch_size
                    offset += batch_size
                    max_batches -= 1
                
                # 如果实际获取的数量超过总数，使用总数
                if len(all_logs) > actual_total:
                    all_logs = all_logs[:actual_total]
                
                if not all_logs:
                    return {
                        "success": True,
                        "total_logs": 0,
                        "total_available": actual_total,
                        "aggregated_groups": [],
                        "has_more": False
                    }
                
                # 执行聚合
                aggregated = _aggregate_logs(all_logs, request.aggregation)
                
                # 检查是否还有更多日志未聚合
                has_more_logs = len(all_logs) < actual_total
        
                return {
                    "success": True,
                    "total_logs": len(all_logs),  # 实际聚合的日志数量
                    "total_available": actual_total,  # 可用的总日志数量
                    "aggregated_groups": aggregated,
                    "has_more": has_more_logs,
                    **(await _maybe_create_case_for_aggregate(request, all_logs, aggregated))
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"日志聚合失败：{str(e)}")


def _aggregate_logs(logs: List[Dict[str, Any]], aggregation: Dict[str, Any]) -> List[Dict[str, Any]]:
    """执行日志聚合"""
    from collections import defaultdict

    # 按设备分组
    device_groups = defaultdict(list)
    for log in logs:
        device = log.get("hostname", "Unknown")
        device_groups[device].append(log)

    # 构建聚合结果
    aggregated_groups = []
    for device, device_logs in device_groups.items():
        # 按日志级别分组
        level_groups = defaultdict(list)
        for log in device_logs:
            level = log.get("level", "unknown")
            level_groups[level].append(log)

        # 构建级别组
        level_group_list = []
        for level, level_logs in level_groups.items():
            # 计算时间范围
            timestamps = [log.get("timestamp", "") for log in level_logs if log.get("timestamp")]
            time_range_str = ""
            if timestamps:
                timestamps.sort()
                time_range_str = f"{timestamps[0].split('T')[1][:5]} - {timestamps[-1].split('T')[1][:5]}"

            level_group_list.append({
                "level": level,
                "count": len(level_logs),
                "time_range": time_range_str,
                "logs": level_logs
            })

        # 按日志级别排序
        level_order = ["Emergencies", "Alert", "Critical", "Error", "Warning", "Notification", "Informational", "Debugging", "unknown"]
        level_group_list.sort(key=lambda x: level_order.index(x["level"]) if x["level"] in level_order else 999)

        aggregated_groups.append({
            "device": device,
            "total_count": len(device_logs),
            "level_groups": level_group_list
        })

    # 按设备日志数量排序
    aggregated_groups.sort(key=lambda x: x["total_count"], reverse=True)

    return aggregated_groups


class DeviceLogAnalysisRequest(BaseModel):
    base_name: str
    base_name_cn: Optional[str] = ""
    device: str
    logs: List[Dict[str, Any]]
    create_case: bool = False
    run_pipeline: bool = False
    site_id: Optional[int] = None
    netbox_device_id: Optional[int] = None
    device_ip: Optional[str] = None
    host: Optional[str] = None
    title: Optional[str] = None


@router.post("/analyze-device")
async def analyze_device_logs(request: DeviceLogAnalysisRequest):
    """使用 AI 分析设备的聚合日志数据"""
    try:
        if not request.logs:
            return {
                "success": False,
                "error": "没有日志数据可供分析"
            }

        # 统计各级别日志数量
        level_counts = {}
        for log in request.logs:
            level = log.get("level", "unknown")
            level_counts[level] = level_counts.get(level, 0) + 1

        # 获取激活的模型配置，根据提供商确定日志数量限制
        from api.models import _models_store
        active_model = None
        for model in _models_store.values():
            if model["is_active"]:
                active_model = model
                break
        
        if not active_model:
            return {
                "success": False,
                "error": "没有激活的模型配置"
            }
        
        # 根据模型提供商设置日志数量限制
        provider = active_model.get("provider", "vllm").lower()
        if provider == "vllm":
            MAX_LOGS_PER_LEVEL = 30  # 本地模型限制为30条
        else:
            MAX_LOGS_PER_LEVEL = 50  # OpenRouter和AIHubMix限制为50条

        # 按级别分组并限制每个级别的日志数量
        level_groups = {}
        total_logs_for_analysis = 0
        has_more_logs = False

        for log in request.logs:
            level = log.get("level", "unknown")
            if level not in level_groups:
                level_groups[level] = []
            
            # 限制每个级别的日志数量
            if len(level_groups[level]) < MAX_LOGS_PER_LEVEL:
                level_groups[level].append(log)
                total_logs_for_analysis += 1
            else:
                has_more_logs = True

        # 构建用于分析的日志列表
        analysis_logs = []
        for level, logs in level_groups.items():
            analysis_logs.extend(logs)

        # 使用 LLM 分析设备日志
        from pathlib import Path
        import json
        prompt_path = Path(__file__).parent.parent / "models" / "prompts" / "device_log_analysis.txt"
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        # 格式化日志数据
        formatted_logs = []
        for log in analysis_logs:
            formatted_log = {
                "hostname": log.get("hostname", "Unknown"),
                "device_ip": log.get("hostname", ""),
                "log_time": log.get("timestamp", ""),
                "raw_message": log.get("message", ""),
                "level": log.get("level", "unknown")
            }
            formatted_logs.append(formatted_log)

        # 构建日志统计字符串
        level_stats = ", ".join([f"{k}: {v}" for k, v in sorted(level_counts.items())])

        # 构建提示文本
        logs_text = "\n".join([f"日志 {i+1}:\n{json.dumps(log, ensure_ascii=False)}" for i, log in enumerate(formatted_logs)])
        
        # 添加日志统计信息到提示中
        context_with_stats = f"""日志统计: {level_stats}
总日志数: {len(request.logs)}
分析日志数: {len(analysis_logs)}
{has_more_logs and '注意: 由于日志数量过多，只分析了部分日志，分析结果可能不全面' or ''}

{logs_text}"""
        
        prompt = prompt_template.replace(
            "{{#context#}}",
            context_with_stats
        ).replace(
            "{base_name}",
            request.base_name_cn or request.base_name
        )

        messages = [
            {
                "role": "system",
                "content": "你是一名网络日志分析专家，只输出分析结果，不输出任何解释或思考过程。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        # 创建临时客户端使用激活的模型
        from models.llm_client import LLMClient
        temp_client = LLMClient(
            api_key=active_model["api_key"],
            base_url=active_model["api_url"],
            model=active_model["model"]
        )
        
        analysis_result = await temp_client.chat_completion(
            messages=messages,
            temperature=0.6
        )

        # 清理分析结果，删除思考字符等不需要的前缀
        cleaned_result = analysis_result
        
        # 删除"思考字符："等前缀
        prefixes_to_remove = ["思考字符：", "思考过程：", "分析过程：", "推理过程：", "思考：", "分析：", "推理："]
        for prefix in prefixes_to_remove:
            if cleaned_result.startswith(prefix):
                cleaned_result = cleaned_result[len(prefix):].strip()
                break
        
        # 如果结果以换行符开始，删除前面的换行符
        cleaned_result = cleaned_result.lstrip('\n\r')

        response = {
            "success": True,
            "result": cleaned_result,
            "device": request.device,
            "log_count": len(request.logs),
            "analyzed_count": len(analysis_logs),
            "has_more": has_more_logs
        }
        response.update(await _maybe_create_case_for_device_analysis(request, cleaned_result))
        return response

    except Exception as e:
        return {
            "success": False,
            "error": f"设备日志分析失败：{str(e)}"
        }


async def _maybe_create_case_for_aggregate(
    request: LogAggregationRequest,
    all_logs: List[Dict[str, Any]],
    aggregated: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not request.create_case:
        return {"case_id": None, "case_code": None}

    dedup_raw = f"log-aggregate|{request.base_name}|{request.time_range}|{request.filter or ''}"
    dedup_key = hashlib.md5(dedup_raw.encode()).hexdigest()
    top_group = aggregated[0] if aggregated else {}
    summary = (
        f"Log aggregate for {request.base_name}, total_logs={len(all_logs)}, "
        f"top_device={top_group.get('device', 'unknown')}, top_count={top_group.get('total_count', 0)}"
    )
    db = SessionLocal()
    try:
        case = await case_orchestrator.intake_case(
            db,
            title=request.title or f"[{request.base_name}] 日志聚合异常",
            source_type="log_aggregate",
            source_system="ELK",
            dedup_key=f"log:{dedup_key}",
            severity="warning",
            site_id=request.site_id,
            netbox_device_id=request.netbox_device_id,
            device_ip=request.device_ip,
            host=request.host,
            summary=summary,
            raw_payload={
                "base_name": request.base_name,
                "time_range": request.time_range,
                "filter": request.filter,
                "sample_logs": all_logs[:20],
            },
            normalized_payload={
                "aggregated_groups": aggregated[:10],
                "total_logs": len(all_logs),
            },
            case_metadata={"source": "logs.aggregate"},
        )
        if request.run_pipeline:
            await case_orchestrator.run_case_pipeline(
                db,
                case_id=case.id,
                base_name=request.base_name,
                log_query=request.filter,
                time_range=request.time_range or "-1d,now",
                log_limit=min(1000, max(200, len(all_logs))),
            )
            db.refresh(case)
        return {"case_id": case.id, "case_code": case.case_code}
    finally:
        db.close()


async def _maybe_create_case_for_device_analysis(
    request: DeviceLogAnalysisRequest,
    analysis_text: str,
) -> Dict[str, Any]:
    if not request.create_case:
        return {"case_id": None, "case_code": None}

    dedup_raw = f"log-device|{request.base_name}|{request.device}|{len(request.logs)}"
    dedup_key = hashlib.md5(dedup_raw.encode()).hexdigest()
    db = SessionLocal()
    try:
        case = await case_orchestrator.intake_case(
            db,
            title=request.title or f"[{request.base_name}] 设备日志分析 {request.device}",
            source_type="device_log_analysis",
            source_system="ELK",
            dedup_key=f"device-log:{dedup_key}",
            severity="warning",
            site_id=request.site_id,
            netbox_device_id=request.netbox_device_id,
            device_ip=request.device_ip or request.device,
            host=request.host or request.device,
            summary=analysis_text[:500],
            raw_payload={
                "device": request.device,
                "base_name": request.base_name,
                "logs": request.logs[:50],
            },
            normalized_payload={
                "analysis": analysis_text[:2000],
                "log_count": len(request.logs),
            },
            case_metadata={"source": "logs.analyze-device"},
        )
        if request.run_pipeline:
            await case_orchestrator.run_case_pipeline(
                db,
                case_id=case.id,
                base_name=request.base_name,
                log_query=request.device,
                time_range="-15m,now",
                log_limit=max(200, min(1000, len(request.logs))),
            )
            db.refresh(case)
        return {"case_id": case.id, "case_code": case.case_code}
    finally:
        db.close()
