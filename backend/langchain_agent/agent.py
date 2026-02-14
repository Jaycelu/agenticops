"""
LangChain Agent - NetOps 智能运维助手

提供 Agent 初始化和执行功能
"""

import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS, SAFE_TOOLS, SENSITIVE_TOOLS

logger = logging.getLogger(__name__)


class NetOpsAgent:
    """NetOps 智能运维助手"""

    def __init__(
        self,
        llm_api_url: str,
        llm_api_key: str,
        model_name: str,
        temperature: float = 0.1
    ):
        """
        初始化 Agent

        Args:
            llm_api_url: LLM API 地址
            llm_api_key: LLM API 密钥
            model_name: 模型名称
            temperature: 温度参数
        """
        self.llm = ChatOpenAI(
            base_url=llm_api_url,
            api_key=llm_api_key or "EMPTY",
            model=model_name,
            temperature=temperature
        )

        self.agent_graph = self._create_agent_graph()

    def _create_agent_graph(self):
        """创建 Agent 图（LangChain 1.2+ API）"""
        # 使用新的 create_agent API
        # 注意：本地 LLM 可能不支持 "auto" tool choice，所以需要特殊处理
        agent_graph = create_agent(
            model=self.llm,
            tools=ALL_TOOLS,
            system_prompt=SYSTEM_PROMPT,
            debug=False  # 关闭调试以减少输出
        )

        return agent_graph

    async def run(
        self,
        input_text: str,
        chat_history: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        运行 Agent

        Args:
            input_text: 用户输入
            chat_history: 聊天历史（可选）

        Returns:
            包含输出和中间步骤的字典
        """
        try:
            # 构建消息列表
            messages = []

            # 添加历史消息
            if chat_history:
                for msg in chat_history:
                    if isinstance(msg, HumanMessage):
                        messages.append({"role": "user", "content": msg.content})
                    elif isinstance(msg, AIMessage):
                        messages.append({"role": "assistant", "content": msg.content})

            # 添加当前用户输入
            messages.append({"role": "user", "content": input_text})

            # 构建输入
            inputs = {"messages": messages}

            # 执行 Agent（使用新的 API）
            intermediate_steps = []
            final_output = ""

            for event in self.agent_graph.stream(inputs, stream_mode="updates"):
                for node_name, node_output in event.items():
                    logger.info(f"Node {node_name}: {node_output}")

                    # 收集中间步骤
                    if node_name == "tools":
                        intermediate_steps.append(node_output)

                    # 获取最终输出
                    if node_name == "agent":
                        messages = node_output.get("messages", [])
                        if messages:
                            last_msg = messages[-1]
                            if isinstance(last_msg, dict) and "content" in last_msg:
                                final_output = last_msg["content"]

            # 如果没有获取到输出，尝试从最后的消息中提取
            if not final_output and intermediate_steps:
                # 从最后一步获取输出
                last_step = intermediate_steps[-1]
                if "messages" in last_step:
                    messages = last_step["messages"]
                    if messages:
                        last_msg = messages[-1]
                        if isinstance(last_msg, dict) and "content" in last_msg:
                            final_output = last_msg["content"]

            return {
                "output": final_output or "处理完成，但没有返回输出。",
                "intermediate_steps": intermediate_steps,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error running agent: {e}", exc_info=True)
            return {
                "output": f"执行失败：{str(e)}",
                "intermediate_steps": [],
                "success": False
            }


# ============================================================================
# 全局 Agent 实例
# ============================================================================

_global_agent: Optional[NetOpsAgent] = None


def init_agent(
    llm_api_url: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> NetOpsAgent:
    """
    初始化全局 Agent 实例

    Args:
        llm_api_url: LLM API 地址（可选，从配置读取）
        llm_api_key: LLM API 密钥（可选，从配置读取）
        model_name: 模型名称（可选，从配置读取）

    Returns:
        NetOps Agent 实例
    """
    global _global_agent

    # 从配置读取默认值
    if not llm_api_url or not model_name:
        from config.settings import settings
        llm_api_url = llm_api_url or settings.llm_api_url
        llm_api_key = llm_api_key or settings.llm_api_key
        model_name = model_name or settings.llm_model_name

    # 创建 Agent
    _global_agent = NetOpsAgent(
        llm_api_url=llm_api_url,
        llm_api_key=llm_api_key,
        model_name=model_name
    )

    logger.info(f"NetOps Agent initialized with model: {model_name}")

    return _global_agent


def get_agent() -> Optional[NetOpsAgent]:
    """
    获取全局 Agent 实例

    Returns:
        NetOps Agent 实例，如果未初始化则返回 None
    """
    return _global_agent