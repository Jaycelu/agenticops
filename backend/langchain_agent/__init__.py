"""
LangChain Agent - NetOps 智能运维助手

这个模块提供了基于 LangChain 的智能体框架，用于：
1. 意图识别（闲聊、诊断、配置）
2. 工具调用（NetBox、Zabbix、ELK、SSH）
3. 自动化编排
"""

from .agent import init_agent, NetOpsAgent
from .simple_agent import init_simple_agent, SimpleNetOpsAgent
from .tools import (
    lookup_netbox_asset,
    run_show_command,
    apply_config_change,
    query_zabbix_alerts,
    search_elk_logs
)

__all__ = [
    "init_agent",
    "NetOpsAgent",
    "init_simple_agent",
    "SimpleNetOpsAgent",
    "lookup_netbox_asset",
    "run_show_command",
    "apply_config_change",
    "query_zabbix_alerts",
    "search_elk_logs"
]