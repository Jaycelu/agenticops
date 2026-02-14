"""
NetOps AI 智能运维工作台 - Streamlit 主应用

提供对话式运维界面，集成 LangChain Agent
"""

import streamlit as st
import sys
import os

# 添加后端路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

# 页面配置
st.set_page_config(
    page_title="NetOps AI 智能运维工作台",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
    }
    .assistant-message {
        background-color: #f5f5f5;
    }
    .tool-call {
        background-color: #fff3e0;
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """初始化会话状态"""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "agent" not in st.session_state:
        st.session_state.agent = None

    if "model_initialized" not in st.session_state:
        st.session_state.model_initialized = False


def init_agent():
    """初始化 Agent"""
    if not st.session_state.model_initialized:
        try:
            from langchain_agent import init_simple_agent
            st.session_state.agent = init_simple_agent()
            st.session_state.model_initialized = True
            return True
        except Exception as e:
            st.error(f"Agent 初始化失败: {e}")
            return False
    return True


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🤖 NetOps AI")
        st.markdown("---")

        # 模型状态
        if st.session_state.model_initialized:
            st.success("✅ 模型已加载")
        else:
            st.warning("⏳ 模型未加载")

        st.markdown("---")

        # 使用说明
        st.subheader("📖 使用说明")
        st.markdown("""
        **支持的对话类型：**

        1. **闲聊** - 打招呼、技术问答
           - 示例：你好、什么是 OSPF

        2. **诊断** - 查询设备状态、排查故障
           - 示例：查看核心交换机状态
           - 示例：检查 192.168.1.1 的告警

        3. **配置** - 修改设备配置
           - 示例：将 G0/1 划入 VLAN 20

        **可用工具：**
        - 📦 NetBox 资产查询
        - 📊 Zabbix 告警查询
        - 🔍 ELK 日志搜索
        - 🔧 SSH 命令执行
        """)

        st.markdown("---")

        # 清空对话
        if st.button("🗑️ 清空对话"):
            st.session_state.messages = []
            st.rerun()


def render_chat():
    """渲染对话界面"""
    st.header("💬 对话式运维")

    # 显示历史消息
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_input():
    """渲染输入框"""
    if prompt := st.chat_input("输入指令：闲聊 / 查状态 / 改配置..."):
        # 添加用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 处理 AI 响应
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("思考中...")

            try:
                # 调用 Agent
                if init_agent():
                    import asyncio
                    result = asyncio.run(st.session_state.agent.run(prompt))

                    if result["success"]:
                        # 显示响应
                        response = result["output"]
                        message_placeholder.markdown(response)

                        # 添加 AI 消息
                        st.session_state.messages.append({"role": "assistant", "content": response})

                        # 显示中间步骤（工具调用）
                        if result["intermediate_steps"]:
                            with st.expander("🔧 工具调用详情"):
                                for step in result["intermediate_steps"]:
                                    tool_name = step.get("tool", "unknown")
                                    tool_args = step.get("args", {})
                                    tool_result = step.get("result", step.get("error", "no result"))

                                    st.markdown(f"""
                                    **工具**: `{tool_name}`
                                    **参数**: `{tool_args}`
                                    **结果**:
                                    ```
                                    {tool_result}
                                    ```
                                    """)
                    else:
                        message_placeholder.error(f"处理失败: {result['output']}")
                else:
                    message_placeholder.error("Agent 未初始化")

            except Exception as e:
                message_placeholder.error(f"发生错误: {e}")
                import traceback
                st.error(traceback.format_exc())


def main():
    """主函数"""
    init_session_state()

    # 渲染侧边栏
    render_sidebar()

    # 渲染对话界面
    render_chat()

    # 渲染输入框
    render_input()


if __name__ == "__main__":
    main()