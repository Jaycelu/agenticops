import httpx
from typing import Dict, Any, Optional
from config.settings import settings
from mcp.base import BaseMCP, MCPResult


class ZabbixMCP(BaseMCP):
    name = "ZabbixMCP"
    description = "Zabbix监控系统集成，用于查询告警、主机和触发器信息"

    def __init__(self):
        super().__init__()
        self.url = settings.zabbix_api_url
        self.username = settings.zabbix_username
        self.password = settings.zabbix_password
        self.auth_token = None
        self.request_id = 0

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": [
                "query_alerts",
                "query_hosts",
                "query_triggers",
                "query_problems"
            ]
        }

    async def _call_api(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """调用Zabbix API"""
        self.request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.request_id,
            "auth": self.auth_token
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, json=payload)
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                raise Exception(f"Zabbix API error: {result['error']}")
            
            return result.get("result", {})

    async def _login(self) -> None:
        """登录Zabbix获取认证token"""
        if self.auth_token:
            return

        payload = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {
                "username": self.username,
                "password": self.password
            },
            "id": 1
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, json=payload)
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                raise Exception(f"Zabbix login error: {result['error']}")
            
            self.auth_token = result.get("result")

    async def execute(self, params: Dict[str, Any]) -> MCPResult:
        action = params.get("action")

        try:
            await self._login()

            if action == "query_alerts":
                return await self._query_alerts(params)
            elif action == "query_hosts":
                return await self._query_hosts(params)
            elif action == "query_triggers":
                return await self._query_triggers(params)
            elif action == "query_problems":
                return await self._query_problems(params)
            elif action == "acknowledge":
                return await self._acknowledge(params)
            else:
                return self._error(f"Unknown action: {action}")
        except Exception as e:
            return self._error(f"Zabbix error: {str(e)}")

    async def _query_alerts(self, params: Dict[str, Any]) -> MCPResult:
        """查询告警列表"""
        # 使用problem.get获取当前未解决的告警
        zabbix_params = {
            "output": "extend",
            "sortfield": ["eventid"],
            "sortorder": "DESC",
            "limit": params.get("limit", 100)
        }

        # 添加筛选条件
        if "severity" in params and params["severity"]:
            zabbix_params["severities"] = [params["severity"]]
        
        if "host" in params and params["host"]:
            zabbix_params["hostids"] = params["host"]

        if "time_from" in params and params["time_from"]:
            zabbix_params["time_from"] = params["time_from"]

        if "time_till" in params and params["time_till"]:
            zabbix_params["time_till"] = params["time_till"]

        problems = await self._call_api("problem.get", zabbix_params)

        # 获取所有eventid，然后查询event以获取主机信息
        event_ids = [p.get("eventid") for p in problems]
        hosts_map = {}
        
        if event_ids:
            # 批量查询事件的主机信息
            events = await self._call_api("event.get", {
                "output": ["eventid", "hosts"],
                "selectHosts": ["host", "name"],
                "eventids": event_ids
            })
            
            # 构建eventid到主机的映射
            for event in events:
                if event.get("hosts") and len(event.get("hosts", [])) > 0:
                    host_name = event.get("hosts", [{}])[0].get("name", "Unknown")
                    host_ip = event.get("hosts", [{}])[0].get("host", "Unknown")
                    hosts_map[event["eventid"]] = {
                        "name": host_name,
                        "host": host_ip
                    }

        result = {
            "count": len(problems),
            "alerts": []
        }

        for problem in problems:
            event_id = problem.get("eventid")
            host_info = hosts_map.get(event_id, {"name": "Unknown", "host": "Unknown"})
            
            # 使用主机名，如果为Unknown则使用主机IP
            display_host = host_info["name"] if host_info["name"] != "Unknown" else host_info["host"]
            
            severity_str = problem.get("severity", "0")
            severity = int(severity_str)
            
            acknowledged = int(problem.get("acknowledged", 0))
            
            # 如果有acknowledged筛选条件，检查是否匹配
            if "acknowledged" in params and params["acknowledged"] is not None:
                if acknowledged != params["acknowledged"]:
                    continue
            
            result["alerts"].append({
                "eventid": problem.get("eventid"),
                "name": problem.get("name"),
                "severity": self._get_severity_name(severity),
                "severity_level": severity,
                "host": display_host,
                "clock": problem.get("clock"),
                "acknowledged": acknowledged,
                "status": "已确认" if acknowledged == 1 else "未确认"
            })
        
        # 更新count为过滤后的数量
        result["count"] = len(result["alerts"])

        return self._success(result, {"action": "query_alerts", "filters": params})

    async def _query_problems(self, params: Dict[str, Any]) -> MCPResult:
        """查询问题列表（包含已解决的问题）"""
        zabbix_params = {
            "output": "extend",
            "selectHosts": ["host", "name"],
            "selectTriggers": ["description", "priority"],
            "sortfield": ["eventid"],
            "sortorder": "DESC",
            "limit": params.get("limit", 100)
        }

        # 添加筛选条件
        if "severity" in params and params["severity"]:
            zabbix_params["filter"] = zabbix_params.get("filter", {})
            zabbix_params["filter"]["severity"] = params["severity"]
        
        if "host" in params and params["host"]:
            zabbix_params["hostids"] = params["host"]

        # 是否包含已解决的问题
        if "recent" in params and params["recent"]:
            zabbix_params["recent"] = params["recent"]

        problems = await self._call_api("event.get", zabbix_params)

        result = {
            "count": len(problems),
            "problems": []
        }

        for problem in problems:
            # 获取主机信息
            host_name = "Unknown"
            host_ip = "Unknown"
            if problem.get("hosts") and len(problem.get("hosts", [])) > 0:
                host_name = problem.get("hosts", [{}])[0].get("name", "Unknown")
                host_ip = problem.get("hosts", [{}])[0].get("host", "Unknown")
            
            # 使用主机IP作为备用
            display_host = host_name if host_name != "Unknown" else host_ip
            
            severity = int(problem.get("severity", 0))

            result["problems"].append({
                "eventid": problem.get("eventid"),
                "name": problem.get("name"),
                "severity": self._get_severity_name(severity),
                "severity_level": severity,
                "host": display_host,
                "clock": problem.get("clock"),
                "r_clock": problem.get("r_clock"),  # 解决时间
                "acknowledged": int(problem.get("acknowledged", 0)),
                "status": "已确认" if int(problem.get("acknowledged", 0)) == 1 else "未确认"
            })

        return self._success(result, {"action": "query_problems", "filters": params})

    async def _query_hosts(self, params: Dict[str, Any]) -> MCPResult:
        """查询主机列表"""
        zabbix_params = {
            "output": ["hostid", "host", "name", "status"],
            "selectInterfaces": ["ip", "type"],
            "selectGroups": ["name"],
            "limit": params.get("limit", 100)
        }

        # 添加筛选条件
        if "search" in params and params["search"]:
            zabbix_params["search"] = {
                "host": params["search"]
            }

        hosts = await self._call_api("host.get", zabbix_params)

        result = {
            "count": len(hosts),
            "hosts": []
        }

        for host in hosts:
            interfaces = host.get("interfaces", [])
            ip_address = interfaces[0].get("ip", "N/A") if interfaces else "N/A"
            groups = [g.get("name", "") for g in host.get("groups", [])]

            result["hosts"].append({
                "hostid": host.get("hostid"),
                "host": host.get("host"),
                "name": host.get("name"),
                "ip": ip_address,
                "status": "启用" if host.get("status") == "0" else "禁用",
                "groups": groups
            })

        return self._success(result, {"action": "query_hosts", "filters": params})

    async def _query_triggers(self, params: Dict[str, Any]) -> MCPResult:
        """查询触发器列表"""
        zabbix_params = {
            "output": ["triggerid", "description", "priority", "status", "value"],
            "selectHosts": ["host", "name"],
            "filter": {
                "value": 1  # 只查询启用的触发器
            },
            "sortfield": ["priority"],
            "sortorder": "DESC",
            "limit": params.get("limit", 100)
        }

        # 添加筛选条件
        if "severity" in params and params["severity"]:
            zabbix_params["filter"]["priority"] = params["severity"]

        if "host" in params and params["host"]:
            zabbix_params["hostids"] = params["host"]

        triggers = await self._call_api("trigger.get", zabbix_params)

        result = {
            "count": len(triggers),
            "triggers": []
        }

        for trigger in triggers:
            host_name = trigger.get("hosts", [{}])[0].get("name", "Unknown") if trigger.get("hosts") else "Unknown"
            priority = int(trigger.get("priority", 0))

            result["triggers"].append({
                "triggerid": trigger.get("triggerid"),
                "description": trigger.get("description"),
                "severity": self._get_severity_name(priority),
                "severity_level": priority,
                "host": host_name,
                "status": "启用" if trigger.get("status") == "0" else "禁用",
                "value": "异常" if trigger.get("value") == 1 else "正常"
            })

        return self._success(result, {"action": "query_triggers", "filters": params})

    def _get_severity_name(self, level: int) -> str:
        """获取严重级别名称"""
        severity_map = {
            0: "未分类",
            1: "信息",
            2: "警告",
            3: "一般严重",
            4: "严重",
            5: "灾难"
        }
        return severity_map.get(level, "未分类")

    async def _acknowledge(self, params: Dict[str, Any]) -> MCPResult:
        """确认告警"""
        event_ids = params.get("event_ids", [])
        message = params.get("message", "已通过NetOps平台确认")
        
        if not event_ids:
            return self._error("No event IDs provided")
        
        # 构建确认参数
        zabbix_params = {
            "eventids": event_ids,
            "message": message,
            "action": 6  # 6 = Acknowledge problem
        }
        
        # 如果提供了确认消息
        if params.get("message"):
            zabbix_params["message"] = params["message"]
        
        result = await self._call_api("event.acknowledge", zabbix_params)
        
        # result["eventids"] 包含已确认的事件ID
        return self._success({
            "count": len(result.get("eventids", [])),
            "event_ids": result.get("eventids", []),
            "message": f"成功确认 {len(result.get('eventids', []))} 个告警"
        }, {"action": "acknowledge", "event_ids": event_ids})