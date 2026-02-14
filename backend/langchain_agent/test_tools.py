"""
测试 LangChain Tools

验证每个工具是否能正常工作
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_agent.tools import (
    lookup_netbox_asset,
    run_show_command,
    query_zabbix_alerts,
    search_elk_logs,
    apply_config_change,
    SAFE_TOOLS,
    SENSITIVE_TOOLS,
    ALL_TOOLS
)


async def test_tools():
    """测试所有工具"""
    print("=" * 60)
    print("测试 LangChain Tools")
    print("=" * 60)

    # 显示工具列表
    print("\n[0] 工具概览")
    print(f"   总工具数: {len(ALL_TOOLS)}")
    print(f"   安全工具: {len(SAFE_TOOLS)}")
    print(f"   敏感工具: {len(SENSITIVE_TOOLS)}")
    print(f"\n   工具列表:")
    for tool in ALL_TOOLS:
        safety = "🔴 敏感" if tool in SENSITIVE_TOOLS else "🟢 安全"
        print(f"   - {tool.name}: {safety}")
        print(f"     {tool.description[:80]}...")

    # 测试 lookup_netbox_asset
    print("\n[1] 测试 lookup_netbox_asset...")
    try:
        result = lookup_netbox_asset.invoke({"query": "test"})
        print(f"✅ 工具调用成功")
        print(f"   结果: {result[:200]}...")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试 query_zabbix_alerts
    print("\n[2] 测试 query_zabbix_alerts...")
    try:
        result = query_zabbix_alerts.invoke({})
        print(f"✅ 工具调用成功")
        print(f"   结果: {result[:200]}...")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")

    # 测试 search_elk_logs
    print("\n[3] 测试 search_elk_logs...")
    try:
        result = search_elk_logs.invoke({"query": "test", "time_range": "1h"})
        print(f"✅ 工具调用成功")
        print(f"   结果: {result[:200]}...")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")

    # 测试 apply_config_change（敏感工具）
    print("\n[4] 测试 apply_config_change（敏感工具）...")
    try:
        result = apply_config_change.invoke({
            "ip": "192.168.1.1",
            "config_lines": ["interface G0/1", "description Test"]
        })
        print(f"✅ 工具调用成功")
        print(f"   结果: {result}")
        if "[CONFIRM_REQUIRED]" in result:
            print("   ✅ 正确返回确认标记")
        else:
            print("   ⚠️  缺少确认标记")
    except Exception as e:
        print(f"❌ 工具调用失败: {e}")

    print("\n" + "=" * 60)
    print("工具测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tools())
