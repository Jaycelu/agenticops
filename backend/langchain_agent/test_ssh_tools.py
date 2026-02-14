"""
测试 SSH 工具

验证 SSH 工具的安全性和功能
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_agent.ssh_tools import (
    run_show_command,
    execute_config_change,
    confirm_and_execute_config,
    is_safe_show_command,
    is_dangerous_command,
    SHOW_COMMAND_WHITELIST,
    DANGEROUS_COMMANDS
)


async def test_ssh_tools():
    """测试 SSH 工具"""
    print("=" * 60)
    print("测试 SSH 工具")
    print("=" * 60)

    # 测试命令安全性检查
    print("\n[0] 测试命令安全性检查...")
    print(f"   白名单命令数: {len(SHOW_COMMAND_WHITELIST)}")
    print(f"   危险命令数: {len(DANGEROUS_COMMANDS)}")

    test_commands = [
        ("show version", True, False),
        ("show interface", True, False),
        ("reload", False, True),
        ("configure terminal", False, True),
        ("display cpu-usage", True, False),
        ("erase startup-config", False, True),
    ]

    print("\n   命令安全性测试:")
    for cmd, expected_safe, expected_dangerous in test_commands:
        is_safe = is_safe_show_command(cmd)
        is_danger = is_dangerous_command(cmd)
        safe_status = "✅" if is_safe == expected_safe else "❌"
        danger_status = "✅" if is_danger == expected_dangerous else "❌"
        print(f"   - {cmd}")
        print(f"     安全检查: {safe_status} (预期: {expected_safe}, 实际: {is_safe})")
        print(f"     危险检查: {danger_status} (预期: {expected_dangerous}, 实际: {is_danger})")

    # 测试 run_show_command
    print("\n[1] 测试 run_show_command...")
    try:
        result = run_show_command.invoke({
            "ip": "192.168.1.1",
            "commands": ["show version"]
        })
        print(f"✅ 工具调用成功")
        print(f"   结果: {result[:200]}...")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")

    # 测试危险命令拒绝
    print("\n[2] 测试危险命令拒绝...")
    try:
        result = run_show_command.invoke({
            "ip": "192.168.1.1",
            "commands": ["reload"]
        })
        print(f"✅ 工具调用成功")
        print(f"   结果: {result}")
        if "拒绝执行危险命令" in result:
            print("   ✅ 正确拒绝危险命令")
        else:
            print("   ❌ 未能正确拒绝危险命令")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")

    # 测试 execute_config_change
    print("\n[3] 测试 execute_config_change（敏感工具）...")
    try:
        result = execute_config_change.invoke({
            "ip": "192.168.1.1",
            "config_lines": ["interface G0/1", "description Test"]
        })
        print(f"✅ 工具调用成功")
        print(f"   结果: {result}")
        if "[CONFIRM_REQUIRED]" in result:
            print("   ✅ 正确返回确认标记")
        else:
            print("   ❌ 缺少确认标记")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")

    # 测试危险配置拒绝
    print("\n[4] 测试危险配置拒绝...")
    try:
        result = execute_config_change.invoke({
            "ip": "192.168.1.1",
            "config_lines": ["erase startup-config"]
        })
        print(f"✅ 工具调用成功")
        print(f"   结果: {result}")
        if "拒绝执行危险命令" in result:
            print("   ✅ 正确拒绝危险配置")
        else:
            print("   ❌ 未能正确拒绝危险配置")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")

    print("\n" + "=" * 60)
    print("SSH 工具测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_ssh_tools())