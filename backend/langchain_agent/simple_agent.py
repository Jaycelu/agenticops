"""
简化的 LangChain Agent - 手动工具调用

为了避免本地 LLM 的工具选择兼容性问题，采用手动工具调用方式
"""

import logging
from typing import Optional, Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)


class SimpleNetOpsAgent:
    """简化的 NetOps 智能运维助手（手动工具调用）"""

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

        # 创建工具映射
        self.tools_map = {tool.name: tool for tool in ALL_TOOLS}

    async def run(
        self,
        input_text: str,
        chat_history: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        运行 Agent（简化版本：手动工具调用）

        Args:
            input_text: 用户输入
            chat_history: 聊天历史（可选）

        Returns:
            包含输出和中间步骤的字典
        """
        try:
            # 构建消息列表
            messages = [
                SystemMessage(content=SYSTEM_PROMPT)
            ]

            # 添加历史消息
            if chat_history:
                messages.extend(chat_history)

            # 添加当前用户输入
            messages.append(HumanMessage(content=input_text))

            # 调用 LLM（第一轮：分析意图）
            response = self.llm.invoke(messages)
            intermediate_steps = []

            # 检查是否需要调用工具
            tool_calls = self._extract_tool_calls(response.content)

            if tool_calls:
                # 执行工具调用
                for tool_call in tool_calls:
                    tool_name = tool_call.get("tool")
                    tool_args = tool_call.get("args", {})

                    if tool_name in self.tools_map:
                        tool = self.tools_map[tool_name]
                        try:
                            # 调用工具
                            tool_result = tool.invoke(tool_args)
                            intermediate_steps.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "result": tool_result
                            })

                            # 将工具结果添加到消息中
                            messages.append(AIMessage(content=f"调用工具 {tool_name}，结果：{tool_result}"))
                        except Exception as e:
                            logger.error(f"Error calling tool {tool_name}: {e}")
                            intermediate_steps.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "error": str(e)
                            })

                # 再次调用 LLM（第二轮：基于工具结果生成回复）
                final_response = self.llm.invoke(messages)
                output = final_response.content
            else:
                # 不需要工具调用，直接返回回复
                output = response.content

            return {
                "output": output,
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

    def _extract_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """
        从 LLM 响应中提取工具调用

        简化版本：检测特定格式的工具调用指令

        Args:
            content: LLM 响应内容

        Returns:
            工具调用列表
        """
        tool_calls = []

        # 检测格式：[TOOL: tool_name(arg1=value1, arg2=value2)]
        import re
        pattern = r'\[TOOL:\s*(\w+)\s*\((.*?)\)\]'

        matches = re.findall(pattern, content)
        for tool_name, args_str in matches:
            # 解析参数
            args = {}
            if args_str:
                # 简单的参数解析（支持 key=value 格式）
                arg_pairs = args_str.split(',')
                for pair in arg_pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        args[key.strip()] = value.strip().strip('"\'').strip()

            tool_calls.append({
                "tool": tool_name,
                "args": args
            })

        return tool_calls


# ============================================================================
# 全局简化 Agent 实例
# ============================================================================

_global_simple_agent: Optional[SimpleNetOpsAgent] = None


def init_simple_agent(
    llm_api_url: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> SimpleNetOpsAgent:
    """
    初始化全局简化 Agent 实例

    Args:
        llm_api_url: LLM API 地址（可选，从配置读取）
        llm_api_key: LLM API 密钥（可选，从配置读取）
        model_name: 模型名称（可选，从配置读取）

    Returns:
        简化的 NetOps Agent 实例
    """
    global _global_simple_agent

    # 从配置读取默认值
    if not llm_api_url or not model_name:
        from config.settings import settings
        llm_api_url = llm_api_url or settings.llm_api_url
        llm_api_key = llm_api_key or settings.llm_api_key
        model_name = model_name or settings.llm_model_name

    # 创建 Agent
    _global_simple_agent = SimpleNetOpsAgent(
        llm_api_url=llm_api_url,
        llm_api_key=llm_api_key,
        model_name=model_name
    )

    logger.info(f"Simple NetOps Agent initialized with model: {model_name}")

    return _global_simple_agent


def get_simple_agent() -> Optional[SimpleNetOpsAgent]:
    """
    获取全局简化 Agent 实例

    Returns:
        简化的 NetOps Agent 实例，如果未初始化则返回 None
    """
    return _global_simple_agent
