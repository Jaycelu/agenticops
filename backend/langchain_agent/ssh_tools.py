"""
SSH 工具 - 用于网络设备的远程操作

提供安全的 SSH 连接和命令执行功能
"""

import logging
from typing import Dict, List, Any, Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ============================================================================
# 安全配置
# ============================================================================

# 允许的 show/display 命令白名单
SHOW_COMMAND_WHITELIST = [
    # 基础信息
    "show version",
    "show running-config",
    "show startup-config",
    "show vlan",
    "show interface",
    "show ip interface brief",
    "show ip route",
    "show ip arp",
    "show mac address-table",
    "show system",

    # 状态检查
    "show processes cpu",
    "show memory",
    "show environment",
    "show power",
    "show temperature",
    "show fans",

    # 接口相关
    "show interface status",
    "show interface counters",
    "show interface description",
    "show interface switchport",
    "show ip interface",

    # 协议相关
    "show spanning-tree",
    "show vtp status",
    "show cdp neighbors",
    "show lldp neighbors",
    "show ip ospf neighbor",
    "show bgp summary",

    # 错误和日志
    "show logging",
    "show logging last",
    "show flash",
    "show tech-support",

    # 华为设备命令
    "display version",
    "display current-configuration",
    "display saved-configuration",
    "display interface",
    "display ip interface brief",
    "display vlan",
    "display device",
    "display cpu-usage",
    "display memory-usage",
    "display logbuffer",
    "display diagnostic-information",
]

# 禁止的危险命令
DANGEROUS_COMMANDS = [
    "reload",
    "reboot",
    "shutdown",
    "erase",
    "delete",
    "format",
    "clear",
    "reset",
    "configure terminal",
    "conf t",
    "system-view",
]


def is_safe_show_command(command: str) -> bool:
    """
    检查命令是否为安全的 show 命令

    Args:
        command: 要检查的命令

    Returns:
        是否安全
    """
    command_lower = command.lower().strip()

    # 检查是否在白名单中
    for whitelist_cmd in SHOW_COMMAND_WHITELIST:
        if command_lower.startswith(whitelist_cmd.lower()):
            return True

    # 检查是否以 show 或 display 开头
    if command_lower.startswith("show ") or command_lower.startswith("display "):
        return True

    return False


def is_dangerous_command(command: str) -> bool:
    """
    检查命令是否为危险命令

    Args:
        command: 要检查的命令

    Returns:
        是否危险
    """
    command_lower = command.lower().strip()

    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in command_lower:
            return True

    return False


# ============================================================================
# SSH 工具
# ============================================================================

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
        # 验证命令安全性
        for cmd in commands:
            if is_dangerous_command(cmd):
                return f"❌ 拒绝执行危险命令: {cmd}"

            if not is_safe_show_command(cmd):
                logger.warning(f"Command may not be safe: {cmd}")
                return f"⚠️  命令不在白名单中: {cmd}。仅允许 show/display 类命令。"

        # 模拟执行（实际应该从 NetBox 获取设备凭证并使用 Paramiko 连接）
        # 这里先返回模拟结果
        output = f"模拟执行 show 命令:\n"
        for cmd in commands:
            output += f"\n>>> {cmd}\n"
            output += f"Command executed successfully on {ip}\n"

        return output

    except Exception as e:
        logger.error(f"Error running show command: {e}")
        return f"执行命令失败：{str(e)}"


@tool
def execute_config_change(ip: str, config_lines: List[str]) -> str:
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
        >>> execute_config_change("192.168.1.1", ["interface G0/1", "description Link_To_Server"])
        "[CONFIRM_REQUIRED] commands: ['interface G0/1', 'description Link_To_Server']"
    """
    try:
        # 验证命令安全性
        for cmd in config_lines:
            if is_dangerous_command(cmd):
                return f"❌ 拒绝执行危险命令: {cmd}"

        # 返回确认标记，不实际执行
        config_str = ", ".join([f"'{cmd}'" for cmd in config_lines])
        return f"[CONFIRM_REQUIRED] commands: [{config_str}]"

    except Exception as e:
        logger.error(f"Error preparing config change: {e}")
        return f"准备配置变更失败：{str(e)}"


@tool
def confirm_and_execute_config(ip: str, config_lines: List[str]) -> str:
    """
    【真正执行】执行配置变更命令（需用户确认后调用）。

    ⚠️ 此工具应该只在用户确认后由系统自动调用，不应该由 Agent 直接调用。

    Args:
        ip: 设备 IP 地址
        config_lines: 配置命令列表

    Returns:
        执行结果
    """
    try:
        # 验证命令安全性
        for cmd in config_lines:
            if is_dangerous_command(cmd):
                return f"❌ 拒绝执行危险命令: {cmd}"

        # 模拟执行（实际应该使用 Paramiko 连接设备并执行配置）
        output = f"模拟执行配置命令:\n"
        for cmd in config_lines:
            output += f"\n>>> {cmd}\n"
            output += f"Config command executed successfully on {ip}\n"

        output += "\n✅ 配置下发成功"

        return output

    except Exception as e:
        logger.error(f"Error executing config: {e}")
        return f"❌ 执行配置失败：{str(e)}"


# ============================================================================
# 工具列表
# ============================================================================

SSH_TOOLS = [
    run_show_command,
    execute_config_change,
    confirm_and_execute_config,
]