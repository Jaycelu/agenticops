"""
简单的 LLM 测试

验证本地 LLM 是否可以正常工作
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from config.settings import settings


async def test_llm():
    """测试 LLM 基础功能"""
    print("=" * 60)
    print("测试本地 LLM")
    print("=" * 60)

    # 初始化 LLM
    print(f"\n[1] 初始化 LLM...")
    print(f"   API URL: {settings.llm_api_url}")
    print(f"   Model: {settings.llm_model_name}")

    try:
        llm = ChatOpenAI(
            base_url=settings.llm_api_url,
            api_key=settings.llm_api_key or "EMPTY",
            model=settings.llm_model_name,
            temperature=0.1
        )
        print("✅ LLM 初始化成功")
    except Exception as e:
        print(f"❌ LLM 初始化失败: {e}")
        return

    # 测试简单对话（不使用工具）
    print("\n[2] 测试简单对话...")
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content="你是一个网络运维专家助手。"),
            HumanMessage(content="你好，请简单介绍一下你自己。")
        ]

        response = llm.invoke(messages)
        print(f"✅ 对话测试成功")
        print(f"   回复: {response.content[:200]}...")
    except Exception as e:
        print(f"❌ 对话测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_llm())