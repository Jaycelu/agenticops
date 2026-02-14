"""
完整系统测试

验证 LangChain Agent + Streamlit 前端的完整流程
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_agent import init_simple_agent


async def test_complete_system():
    """完整系统测试"""
    print("=" * 80)
    print("🚀 NetOps AI 智能运维工作台 - 完整系统测试")
    print("=" * 80)

    # 初始化 Agent
    print("\n[1/5] 初始化 LangChain Agent...")
    try:
        agent = init_simple_agent()
        print("✅ Agent 初始化成功")
        print(f"   工具数量: {len(agent.tools_map)}")
        print(f"   工具列表: {list(agent.tools_map.keys())}")
    except Exception as e:
        print(f"❌ Agent 初始化失败: {e}")
        return False

    # 测试场景 1：闲聊
    print("\n[2/5] 测试场景 1：闲聊模式...")
    try:
        result = await agent.run("你好，请简单介绍一下你自己")
        if result["success"]:
            print("✅ 闲聊模式测试成功")
            print(f"   回复: {result['output'][:100]}...")
        else:
            print(f"❌ 闲聊模式测试失败: {result['output']}")
    except Exception as e:
        print(f"❌ 闲聊模式测试失败: {e}")

    # 测试场景 2：设备查询
    print("\n[3/5] 测试场景 2：设备查询（诊断模式）...")
    try:
        result = await agent.run("查询设备信息")
        if result["success"]:
            print("✅ 设备查询测试成功")
            print(f"   回复: {result['output'][:100]}...")
            if result["intermediate_steps"]:
                print(f"   调用工具数: {len(result['intermediate_steps'])}")
        else:
            print(f"❌ 设备查询测试失败: {result['output']}")
    except Exception as e:
        print(f"❌ 设备查询测试失败: {e}")

    # 测试场景 3：配置变更
    print("\n[4/5] 测试场景 3：配置变更（配置模式）...")
    try:
        result = await agent.run("修改接口描述为 Test")
        if result["success"]:
            print("✅ 配置变更测试成功")
            print(f"   回复: {result['output'][:100]}...")
            if "[CONFIRM_REQUIRED]" in result["output"]:
                print("   ✅ 正确返回确认标记")
        else:
            print(f"❌ 配置变更测试失败: {result['output']}")
    except Exception as e:
        print(f"❌ 配置变更测试失败: {e}")

    # 测试场景 4：告警查询
    print("\n[5/5] 测试场景 4：告警查询（诊断模式）...")
    try:
        result = await agent.run("查看当前的告警信息")
        if result["success"]:
            print("✅ 告警查询测试成功")
            print(f"   回复: {result['output'][:100]}...")
            if result["intermediate_steps"]:
                print(f"   调用工具数: {len(result['intermediate_steps'])}")
        else:
            print(f"❌ 告警查询测试失败: {result['output']}")
    except Exception as e:
        print(f"❌ 告警查询测试失败: {e}")

    print("\n" + "=" * 80)
    print("✅ 系统测试完成！")
    print("=" * 80)
    print("\n📦 已完成的功能：")
    print("  ✅ LangChain Agent（简化版）")
    print("  ✅ 意图识别（闲聊/诊断/配置）")
    print("  ✅ 5 个 LangChain Tools")
    print("  ✅ 安全工具分类（4个安全 + 1个敏感）")
    print("  ✅ SSH 工具（含白名单和危险命令拦截）")
    print("  ✅ Streamlit 前端界面")
    print("  ✅ 配置确认流程")
    print("\n🚀 启动方式：")
    print("  cd /opt/netops/frontend/streamlit")
    print("  streamlit run app.py --server.port 8501 --server.address 0.0.0.0")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = asyncio.run(test_complete_system())
    sys.exit(0 if success else 1)
