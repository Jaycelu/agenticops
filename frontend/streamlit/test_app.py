"""
测试 Streamlit 应用导入

验证应用能否正常导入和初始化
"""

import sys
import os

# 添加后端路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

print("=" * 60)
print("测试 Streamlit 应用导入")
print("=" * 60)

# 测试导入 Streamlit
print("\n[1] 测试 Streamlit 导入...")
try:
    import streamlit as st
    print("✅ Streamlit 导入成功")
    print(f"   版本: {st.__version__}")
except Exception as e:
    print(f"❌ Streamlit 导入失败: {e}")
    sys.exit(1)

# 测试导入 LangChain Agent
print("\n[2] 测试 LangChain Agent 导入...")
try:
    from langchain_agent import init_simple_agent
    print("✅ LangChain Agent 导入成功")
except Exception as e:
    print(f"❌ LangChain Agent 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 Agent 初始化
print("\n[3] 测试 Agent 初始化...")
try:
    import asyncio

    async def test_agent():
        agent = init_simple_agent()
        if agent:
            print("✅ Agent 初始化成功")
            print(f"   工具数量: {len(agent.tools_map)}")
            print(f"   工具列表: {list(agent.tools_map.keys())}")
            return True
        else:
            print("❌ Agent 初始化失败")
            return False

    result = asyncio.run(test_agent())
    if not result:
        sys.exit(1)

except Exception as e:
    print(f"❌ Agent 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)
print("\n现在可以运行 Streamlit 应用：")
print("  cd /opt/netops/frontend/streamlit")
print("  streamlit run app.py")
print("=" * 60)