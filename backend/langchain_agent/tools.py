"""
LangChain Tools - 将 MCP 工具转换为 LangChain 兼容格式

安全工具：lookup_netbox_asset, run_show_command, query_zabbix_alerts, search_elk_logs
敏感工具：apply_config_change
"""

from langchain_core.tools import tool
from typing import List, Dict, Any, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)


def run_async(coro):
    """运行异步协程的辅助函数"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的循环，创建新的
        return asyncio.run(coro)
    else:
        # 有运行中的循环，使用 asyncio.run_coroutine_threadsafe 或创建新循环
        import concurrent.futures
        import threading
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()


# ============================================================================
# 安全工具（只读）
# ============================================================================

@tool
def lookup_netbox_asset(query: str) -> str:
    """
    查询 NetBox 中的设备信息，获取设备 IP、平台、登录凭证等。

    当需要操作具体设备时，必须先调用此工具获取设备信息。

    Args:
        query: 设备名称（如 Core-Switch-01）、IP 地址或角色（如 core）

    Returns:
        设备信息字符串，包含：name, ip, platform, role, username, password

    Example:
        >>> lookup_netbox_asset("Core-Switch-01")
        "name: Core-Switch-01, ip: 192.168.1.1, platform: cisco_ios, role: core"
    """
    try:
        from mcp.netbox_mcp import NetBoxMCP
        netbox_mcp = NetBoxMCP()

        # 使用辅助函数运行异步方法
        result = run_async(netbox_mcp.execute({
            "action": "query_devices",
            "name": query,
            "limit": 1
        }))

        if result.success and result.data.get("count", 0) > 0:
            device = result.data["devices"][0]
            return f"""name: {device.get('name')}
ip: {str(device.get('primary_ip', 'N/A')).split('/')[0] if device.get('primary_ip') else 'N/A'}
platform: {device.get('platform', 'unknown')}
role: {device.get('role', 'unknown')}
site: {device.get('site', 'unknown')}"""
        else:
            return f"未找到设备：{query}，请确认设备名称或 IP 地址。"

    except Exception as e:
        logger.error(f"Error querying NetBox: {e}")
        return f"查询 NetBox 失败：{str(e)}"


@tool
def run_show_command(ip: str, commands: List[str]) -> str:
    """
    在设备上执行 show/display 类命令，用于故障排查和状态查询。

    ⚠️ 安全工具：只能执行查看命令，不能修改配置。

    Args:
        ip: 设备 IP 地址
        commands: 命令列表，例如 ["show version", "show ip int br", "display interface"]

    Returns:
        命令执行结果的原始输出

    Example:
        >>> run_show_command("192.168.1.1", ["show interfaces G0/1"])
        "Interface GigabitEthernet0/1 is UP, Line protocol is UP..."
    """
    try:
        from services.script_executor import script_executor
        from models.llm_client import LLMClient

        # 执行 show 命令
        output = script_executor.execute_show_commands(
            device_ip=ip,
            commands=commands
        )

        if output:
            return output
        else:
            return f"命令执行成功，但没有返回输出。"

    except Exception as e:
        logger.error(f"Error running show command: {e}")
        return f"执行命令失败：{str(e)}"


@tool
def query_zabbix_alerts(device_name: Optional[str] = None, severity: Optional[str] = None) -> str:
    """
    查询 Zabbix 告警信息。

    Args:
        device_name: 设备名称（可选）
        severity: 告警级别（可选），如 "High", "Warning", "Information"

    Returns:
        告警信息列表

    Example:
        >>> query_zabbix_alerts(device_name="Core-Switch-01", severity="High")
        "告警1: Interface Down on Core-Switch-01\n告警2: High CPU Usage..."
    """
    try:
        from mcp.zabbix_mcp import ZabbixMCP
        zabbix_mcp = ZabbixMCP()

        # 使用辅助函数运行异步方法
        severity_map = {
            "unclassified": 0,
            "information": 1,
            "warning": 2,
            "average": 3,
            "high": 4,
            "disaster": 5,
        }
        sev = severity_map.get(str(severity).lower()) if severity else None
        result = run_async(zabbix_mcp.execute({
            "action": "query_alerts",
            "host": device_name,
            "severity": sev,
            "limit": 10
        }))

        if result.success and result.data:
            alerts = result.data.get("alerts", [])
            if not alerts:
                return "没有找到符合条件的告警。"

            alert_text = []
            for alert in alerts[:5]:  # 最多返回 5 条
                alert_text.append(
                    f"- {alert.get('name', 'N/A')} "
                    f"({alert.get('severity', 'N/A')}) "
                    f"at {alert.get('clock', 'N/A')}"
                )

            return "\n".join(alert_text)
        else:
            return "查询 Zabbix 告警失败。"

    except Exception as e:
        logger.error(f"Error querying Zabbix alerts: {e}")
        return f"查询 Zabbix 告警失败：{str(e)}"


@tool
def search_elk_logs(query: str, time_range: str = "1h") -> str:
    """
    搜索 ELK 日志。

    Args:
        query: 搜索查询条件，例如 "interface down", "CRC error"
        time_range: 时间范围，例如 "1h", "24h", "7d"

    Returns:
        日志搜索结果

    Example:
        >>> search_elk_logs("interface G0/1 down", "1h")
        "2024-01-27 10:00:00: Interface G0/1 is down..."
    """
    try:
        from mcp.elk_mcp import ELKMCP
        elk_mcp = ELKMCP()

        # 使用辅助函数运行异步方法
        result = run_async(elk_mcp.execute({
            "action": "query_logs",
            "query": query,
            "time_range": time_range,
            "limit": 10
        }))

        if result.success and result.data:
            logs = result.data.get("logs", [])
            if not logs:
                return f"在 {time_range} 内没有找到匹配的日志。"

            log_text = []
            for log in logs[:5]:  # 最多返回 5 条
                log_text.append(
                    f"- {log.get('timestamp', 'N/A')}: "
                    f"{log.get('message', 'N/A')}"
                )

            return "\n".join(log_text)
        else:
            return "搜索 ELK 日志失败。"

    except Exception as e:
        logger.error(f"Error searching ELK logs: {e}")
        return f"搜索 ELK 日志失败：{str(e)}"


# ============================================================================
# 敏感工具（写操作）
# ============================================================================

@tool
def apply_config_change(ip: str, config_lines: List[str]) -> str:
    """
    【高危】在设备上执行配置变更命令。

    ⚠️ 敏感工具：需要用户确认后才能执行。

    此工具不会真正执行配置，而是返回 `[CONFIRM_REQUIRED]` 标记，
    等待用户确认后再调用实际的执行函数。

    Args:
        ip: 设备 IP 地址
        config_lines: 配置命令列表，例如 ["interface G0/1", "description Link_To_Server"]

    Returns:
        包含 `[CONFIRM_REQUIRED]` 标记的配置计划字符串

    Example:
        >>> apply_config_change("192.168.1.1", ["interface G0/1", "description Link_To_Server"])
        "[CONFIRM_REQUIRED] commands: ['interface G0/1', 'description Link_To_Server']"
    """
    try:
        # 返回确认标记，不实际执行
        config_str = ", ".join([f"'{cmd}'" for cmd in config_lines])
        return f"[CONFIRM_REQUIRED] commands: [{config_str}]"

    except Exception as e:
        logger.error(f"Error preparing config change: {e}")
        return f"准备配置变更失败：{str(e)}"


# ============================================================================
# 工具集合
# ============================================================================

SAFE_TOOLS = [
    lookup_netbox_asset,
    run_show_command,
    query_zabbix_alerts,
    search_elk_logs
]

SENSITIVE_TOOLS = [
    apply_config_change
]

ALL_TOOLS = SAFE_TOOLS + SENSITIVE_TOOLS
