"""
测试 LangChain Agent

验证 Agent 是否可以正常初始化和运行
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_agent import init_agent


async def test_agent():
    """测试 Agent 基础功能"""
    print("=" * 60)
    print("测试 LangChain Agent")
    print("=" * 60)

    # 初始化 Agent
    print("\n[1] 初始化 Agent...")
    try:
        agent = init_agent()
        print("✅ Agent 初始化成功")
    except Exception as e:
        print(f"❌ Agent 初始化失败: {e}")
        return

    # 测试闲聊模式
    print("\n[2] 测试闲聊模式...")
    try:
        result = await agent.run("你好，请介绍一下你自己")
        print(f"✅ 闲聊模式测试成功")
        print(f"   回复: {result['output'][:100]}...")
    except Exception as e:
        print(f"❌ 闲聊模式测试失败: {e}")

    # 测试工具加载
    print("\n[3] 验证工具加载...")
    try:
        from langchain_agent.tools import ALL_TOOLS, SAFE_TOOLS, SENSITIVE_TOOLS
        print(f"✅ 工具加载成功")
        print(f"   - 总工具数: {len(ALL_TOOLS)}")
        print(f"   - 安全工具: {len(SAFE_TOOLS)}")
        print(f"   - 敏感工具: {len(SENSITIVE_TOOLS)}")
        print(f"   - 工具列表: {[tool.name for tool in ALL_TOOLS]}")
    except Exception as e:
        print(f"❌ 工具加载失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_agent())