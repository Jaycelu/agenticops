import httpx
from typing import Dict, Any, Optional
from mcp.base import BaseMCP, MCPResult
from services.integration_config_service import integration_config_service
from services.log_scope_service import log_scope_service


class ELKMCP(BaseMCP):
    name = "ELKMCP"
    description = "ELK日志系统集成，用于查询和分析日志数据"

    def __init__(self):
        super().__init__()
        self.auth_header = None

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": [
                "query_logs",
                "query_logs_by_base",
                "get_base_configs"
            ]
        }

    def _get_auth_header(self) -> str:
        """获取认证header"""
        import base64
        config = integration_config_service.get_elk_runtime_config()
        if not config.get("enabled") or not config.get("url") or not config.get("username") or not config.get("password"):
            raise RuntimeError("elk_not_configured")
        credentials = f"{config['username']}:{config['password']}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _get_url(self) -> str:
        config = integration_config_service.get_elk_runtime_config()
        if not config.get("enabled") or not config.get("url"):
            raise RuntimeError("elk_not_configured")
        return config["url"]

    def _resolve_scope(self, params: Dict[str, Any]) -> Dict[str, Any]:
        scope = log_scope_service.resolve_scope(
            scope_key=params.get("scope_key"),
            base_name=params.get("base_name"),
            netbox_site_id=params.get("netbox_site_id"),
            site_code=params.get("site_code"),
            site_name=params.get("site_name"),
        )
        if not scope:
            raise RuntimeError("log_scope_not_found")
        return scope

    async def execute(self, params: Dict[str, Any]) -> MCPResult:
        action = params.get("action")

        try:
            if action == "query_logs":
                return await self._query_logs(params)
            elif action == "query_logs_by_base":
                return await self._query_logs_by_base(params)
            elif action == "get_base_configs":
                return self._get_base_configs()
            else:
                return self._error(f"Unknown action: {action}")
        except Exception as e:
            return self._error(f"ELK error: {str(e)}")

    async def _query_logs(self, params: Dict[str, Any]) -> MCPResult:
        """查询日志数据"""
        query = params.get("query", "*")
        time_range = params.get("time_range", "-1d,now")
        limit = params.get("limit", 100)
        offset = params.get("offset", 0)

        # 构建查询参数
        query_params = {
            "query": query,
            "time_range": time_range,
            "limit": limit,
            "offset": offset,
            "mode": "elastic",
            "highlight": "true"
        }

        headers = {
            "Authorization": self._get_auth_header()
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                self._get_url(),
                headers=headers,
                params=query_params
            )
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                raise Exception(f"ELK API error: {result['error']}")

            return self._success({
                "query": query,
                "time_range": time_range,
                "total": result.get("total", 0),
                "logs": result.get("data", [])
            }, {"action": "query_logs", "filters": params})

    async def _query_logs_by_base(self, params: Dict[str, Any]) -> MCPResult:
        """按日志范围查询日志数据"""
        limit = params.get("limit", 100)
        custom_time_range = params.get("time_range", None)
        custom_filter = params.get("custom_filter", None)

        scope = self._resolve_scope(params)
        scope_key = scope["scope_key"]

        # 使用自定义筛选条件或范围默认筛选条件
        query = custom_filter if custom_filter else scope["query_filter"]
        time_range = custom_time_range if custom_time_range else scope["default_time_range"]

        # 构建查询参数（使用 Dify 工作流的参数格式）
        query_params = {
            "domain": "ops",
            "time_range": time_range,
            "operator": "admin",
            "query": query,
            "category": "search",
            "background": "false",
            "highlight": "false",
            "fields": "false",
            "timeline": "false",
            "size": str(limit)
        }

        headers = {
            "Authorization": self._get_auth_header()
        }

        import logging
        logger = logging.getLogger(__name__)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                logger.info(f"Querying ELK: scope={scope_key}, query={query[:200]}...")
                response = await client.get(
                    self._get_url(),
                    headers=headers,
                    params=query_params
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise Exception(f"ELK API error: {result['error']}")

                # 解析日志数据（从 results.sheets.rows 获取）
                logs_data = result.get("results", {}).get("sheets", {}).get("rows", [])
                
                # 如果没有日志数据，返回提示信息
                if not logs_data:
                    return self._success({
                        "base": scope_key,
                        "base_name_cn": scope["display_name"],
                        "query": query,
                        "time_range": time_range,
                        "total": 0,
                        "logs": [],
                        "no_logs_hint": True,
                        "scope_key": scope_key,
                        "site_code": scope.get("site_code_snapshot"),
                        "site_name": scope.get("site_name_snapshot"),
                    }, {"action": "query_logs_by_base", "filters": params})
                
                parsed_logs = []
                
                for log in logs_data:
                    # 转换时间戳（使用上海时区）
                    timestamp = log.get("timestamp", 0)
                    if timestamp:
                        from datetime import datetime
                        from zoneinfo import ZoneInfo
                        # 使用上海时区转换时间戳
                        local_tz = ZoneInfo("Asia/Shanghai")
                        timestamp_str = datetime.fromtimestamp(timestamp / 1000, tz=local_tz).isoformat()
                    else:
                        timestamp_str = ""
                    
                    parsed_log = {
                        "timestamp": timestamp_str,
                        "hostname": log.get("hostname", "Unknown"),
                        "device_ip": self._extract_device_ip(log.get("hostname", ""), log.get("raw_message", "")),
                        "message": log.get("raw_message", ""),
                        "level": self._extract_log_level(log.get("raw_message", "")),
                        "raw": log
                    }
                    parsed_logs.append(parsed_log)

                total = result.get("results", {}).get("total_hits", 0)

                return self._success({
                    "base": scope_key,
                    "base_name_cn": scope["display_name"],
                    "query": query,
                    "time_range": time_range,
                    "total": total,
                    "logs": parsed_logs,
                    "scope_key": scope_key,
                    "site_code": scope.get("site_code_snapshot"),
                    "site_name": scope.get("site_name_snapshot"),
                }, {"action": "query_logs_by_base", "filters": params})
            
            except httpx.TimeoutException:
                # 连接超时，返回提示信息
                return self._success({
                    "base": scope_key,
                    "base_name_cn": scope["display_name"],
                    "query": query,
                    "time_range": time_range,
                    "total": 0,
                    "logs": [],
                    "timeout_error": True,
                    "scope_key": scope_key,
                    "site_code": scope.get("site_code_snapshot"),
                    "site_name": scope.get("site_name_snapshot"),
                }, {"action": "query_logs_by_base", "filters": params})
            except httpx.HTTPStatusError as e:
                # HTTP 错误
                raise Exception(f"ELK HTTP error: {e.response.status_code}")
            except Exception as e:
                # 其他错误
                raise Exception(f"ELK query error: {str(e)}")

    def _get_base_configs(self) -> MCPResult:
        """获取所有日志范围配置（兼容旧 bases 接口）"""
        scopes = log_scope_service.list_scopes(enabled_only=True)
        return self._success({
            "bases": [
                {
                    "key": scope["scope_key"],
                    "name": scope["display_name"],
                    "filter": scope["query_filter"],
                    "time_range": scope["default_time_range"],
                    "site_code": scope.get("site_code_snapshot"),
                    "site_name": scope.get("site_name_snapshot"),
                    "aliases": scope.get("aliases") or [],
                }
                for scope in scopes
            ]
        }, {"action": "get_base_configs"})

    def _extract_log_level(self, message: str) -> str:
        """从日志消息中提取日志级别"""
        import re
        
        # 匹配 <184>, <185>, <186>, <187> 等日志级别
        match = re.search(r'<(\d+)>', message)
        if match:
            level_code = int(match.group(1))
            level_map = {
                184: "Emergencies",
                185: "Alert",
                186: "Critical",
                187: "Error",
                188: "Warning",
                189: "Notification",
                190: "Informational",
                191: "Debugging"
            }
            return level_map.get(level_code, "unknown")
        
        return "unknown"

    def _extract_device_ip(self, hostname: str, raw_message: str) -> str:
        """从 hostname 或 raw_message 中提取设备 IP 地址"""
        import re
        
        # 1. 首先检查 hostname 是否已经是 IP 地址格式
        if hostname and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
            return hostname
        
        # 2. 从 raw_message 中的 DevIP= 字段提取
        devip_match = re.search(r'DevIP=(\d+\.\d+\.\d+\.\d+)', raw_message)
        if devip_match:
            return devip_match.group(1)
        
        # 3. 从 raw_message 中直接提取 IP 地址
        ip_match = re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', raw_message)
        if ip_match:
            return ip_match.group(0)
        
        return "Unknown"
