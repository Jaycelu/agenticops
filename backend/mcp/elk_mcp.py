import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from config.settings import settings
from mcp.base import BaseMCP, MCPResult


class ELKMCP(BaseMCP):
    name = "ELKMCP"
    description = "ELK日志系统集成，用于查询和分析日志数据"

    def __init__(self):
        super().__init__()
        self.url = settings.elk_url
        self.username = settings.elk_username
        self.password = settings.elk_password
        self.auth_header = None

        # 基地配置
        self.base_configs = {
            "deyang": {
                "name": "德阳基地",
                "filter": '((hostname:10.128.* AND appname:syslog) AND NOT hostname:10.128.225.*) AND NOT hostname:10.128.253.24',
                "time_range": "-1d,now"
            },
            "chuzhou": {
                "name": "滁州基地",
                "filter": '(((((hostname:172.31.13.*) OR (hostname:10.13.*)) AND tag:syslog) AND NOT hostname:10.13.225.*) AND NOT hostname:10.13.241.2) AND NOT hostname:10.13.241.3',
                "time_range": "-1d,now"
            },
            "huaian_phase1": {
                "name": "淮安一期",
                "filter": '((((hostname:10.14.* AND NOT hostname:10.14.226.*) AND NOT hostname:10.14.225.*) AND NOT hostname:10.14.250.254) AND NOT hostname:10.14.253.252) AND NOT hostname:10.14.253.253',
                "time_range": "-1d,now"
            },
            "huaian_phase2": {
                "name": "淮安二期",
                "filter": 'hostname:10.15.*',
                "time_range": "-1d,now"
            },
            "huaian_phase3": {
                "name": "淮安三期",
                "filter": '(hostname:10.21.* AND NOT hostname:10.21.254.249) AND NOT hostname:10.21.254.250',
                "time_range": "-1d,now"
            },
            "huaian_phase4": {
                "name": "淮安四期",
                "filter": '((hostname:10.16.* AND appname:syslog) AND NOT hostname:10.16.251.5) AND NOT hostname:10.16.251.6',
                "time_range": "-1d,now"
            },
            "huaian_phase5": {
                "name": "淮安五期",
                "filter": 'hostname:10.22.*',
                "time_range": "-1d,now"
            },
            "qinghai_components": {
                "name": "青海组件",
                "filter": '((hostname:10.66.*) OR (hostname:172.31.66.*)) AND NOT hostname:10.66.226.* AND NOT hostname:10.66.225.*',
                "time_range": "-1d,now"
            },
            "qinghai_crystal": {
                "name": "青海拉晶",
                "filter": '(((((hostname:10.65.*) OR (hostname:172.31.65.*) OR (hostname:172.31.67.*)) AND NOT hostname:10.65.226.* AND NOT hostname:10.65.225.*) AND NOT hostname:10.65.32.253) AND NOT hostname:172.31.65.3) AND NOT hostname:172.31.65.2',
                "time_range": "-1d,now"
            },
            "suqian": {
                "name": "宿迁基地",
                "filter": '(hostname:10.23.* AND NOT hostname:10.23.226.*) AND NOT hostname:10.23.225.*',
                "time_range": "-1d,now"
            },
            "yangzhou": {
                "name": "扬州基地",
                "filter": '(((hostname:10.17.* AND NOT hostname:10.17.226.*) AND NOT hostname:10.17.225.*) AND NOT hostname:10.17.224.249) AND NOT hostname:10.17.224.250',
                "time_range": "-1d,now"
            },
            "yiwu": {
                "name": "义乌基地",
                "filter": '(((hostname:10.12.* AND NOT hostname:10.12.226.*) AND NOT hostname:10.12.225.* AND NOT hostname:10.12.243.*) AND NOT hostname:10.12.241.64) AND NOT hostname:10.12.241.65',
                "time_range": "-1d,now"
            }
        }

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
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

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
                self.url,
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
        """按基地查询日志数据"""
        base_name = params.get("base_name", "deyang")
        limit = params.get("limit", 100)
        offset = params.get("offset", 0)
        custom_time_range = params.get("time_range", None)
        custom_filter = params.get("custom_filter", None)

        # 获取基地配置
        if base_name not in self.base_configs:
            return self._error(f"Unknown base: {base_name}")

        base_config = self.base_configs[base_name]
        
        # 使用自定义筛选条件或基地默认筛选条件
        query = custom_filter if custom_filter else base_config["filter"]
        time_range = custom_time_range if custom_time_range else base_config["time_range"]

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
                logger.info(f"Querying ELK: base={base_name}, query={query[:200]}...")
                response = await client.get(
                    self.url,
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
                        "base": base_name,
                        "base_name_cn": base_config["name"],
                        "query": query,
                        "time_range": time_range,
                        "total": 0,
                        "logs": [],
                        "no_logs_hint": True
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
                    "base": base_name,
                    "base_name_cn": base_config["name"],
                    "query": query,
                    "time_range": time_range,
                    "total": total,
                    "logs": parsed_logs
                }, {"action": "query_logs_by_base", "filters": params})
            
            except httpx.TimeoutException:
                # 连接超时，返回提示信息
                return self._success({
                    "base": base_name,
                    "base_name_cn": base_config["name"],
                    "query": query,
                    "time_range": time_range,
                    "total": 0,
                    "logs": [],
                    "timeout_error": True
                }, {"action": "query_logs_by_base", "filters": params})
            except httpx.HTTPStatusError as e:
                # HTTP 错误
                raise Exception(f"ELK HTTP error: {e.response.status_code}")
            except Exception as e:
                # 其他错误
                raise Exception(f"ELK query error: {str(e)}")

    def _get_base_configs(self) -> MCPResult:
        """获取所有基地配置"""
        return self._success({
            "bases": [
                {
                    "key": key,
                    "name": config["name"],
                    "filter": config["filter"],
                    "time_range": config["time_range"]
                }
                for key, config in self.base_configs.items()
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