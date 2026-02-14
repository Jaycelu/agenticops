"""
测试简化的 LangChain Agent

验证简化版 Agent 是否可以正常工作
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_agent import init_simple_agent


async def test_simple_agent():
    """测试简化版 Agent 基础功能"""
    print("=" * 60)
    print("测试简化版 LangChain Agent")
    print("=" * 60)

    # 初始化 Agent
    print("\n[1] 初始化简化版 Agent...")
    try:
        agent = init_simple_agent()
        print("✅ Agent 初始化成功")
    except Exception as e:
        print(f"❌ Agent 初始化失败: {e}")
        return

    # 测试闲聊模式
    print("\n[2] 测试闲聊模式...")
    try:
        result = await agent.run("你好，请简单介绍一下你自己")
        print(f"✅ 闲聊模式测试成功")
        print(f"   回复: {result['output'][:200]}...")
        print(f"   中间步骤数: {len(result['intermediate_steps'])}")
    except Exception as e:
        print(f"❌ 闲聊模式测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试工具加载
    print("\n[3] 验证工具加载...")
    try:
        print(f"✅ 工具加载成功")
        print(f"   - 工具列表: {list(agent.tools_map.keys())}")
    except Exception as e:
        print(f"❌ 工具加载失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_simple_agent())
