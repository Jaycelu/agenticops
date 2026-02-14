from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key or "EMPTY"
        self.base_url = base_url
        self.model = model
        self._init_client()

    def _init_client(self):
        """初始化OpenAI客户端"""
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60.0  # 默认60秒超时
        )

    def update_config(self, api_key: str = "", base_url: str = "", model: str = ""):
        """更新配置"""
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url
        if model:
            self.model = model
        self._init_client()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        max_retries: int = 2
    ) -> str:
        """
        调用LLM进行对话，支持重试机制

        Args:
            messages: 对话消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 超时时间（秒）
            max_retries: 最大重试次数

        Returns:
            AI响应文本
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # 使用asyncio.wait_for替代asyncio.timeout（兼容Python 3.10）
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    ),
                    timeout=timeout
                )
                return response.choices[0].message.content

            except asyncio.TimeoutError:
                last_error = f"LLM timeout after {timeout}s (attempt {attempt + 1}/{max_retries + 1})"
                logger.warning(last_error)
                if attempt < max_retries:
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避
                    continue

            except Exception as e:
                last_error = f"LLM error: {str(e)} (attempt {attempt + 1}/{max_retries + 1})"
                logger.error(last_error)
                if attempt < max_retries:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue

        raise Exception(last_error)

    async def chat_completion_with_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        timeout: float = 60.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        调用LLM进行对话，返回JSON格式结果，支持重试机制

        Args:
            messages: 对话消息列表
            temperature: 温度参数
            timeout: 超时时间（秒）
            max_retries: 最大重试次数

        Returns:
            AI响应的JSON字典
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                print(f"[DEBUG] LLM API call attempt {attempt + 1}/{max_retries + 1}, timeout={timeout}s")
                # 使用asyncio.wait_for替代asyncio.timeout（兼容Python 3.10）
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        response_format={"type": "json_object"}
                    ),
                    timeout=timeout
                )
                print(f"[DEBUG] LLM API call succeeded")
                import json
                return json.loads(response.choices[0].message.content)

            except asyncio.TimeoutError:
                last_error = f"LLM JSON timeout after {timeout}s (attempt {attempt + 1}/{max_retries + 1})"
                logger.warning(last_error)
                if attempt < max_retries:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue

            except Exception as e:
                last_error = f"LLM JSON error: {str(e)} (attempt {attempt + 1}/{max_retries + 1})"
                logger.error(last_error)
                if attempt < max_retries:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue

        raise Exception(last_error)

    async def chat(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        max_retries: int = 2
    ) -> str:
        """
        兼容性方法：接受单个prompt字符串，转换为messages格式

        Args:
            prompt: 提示文本
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 超时时间（秒）
            max_retries: 最大重试次数

        Returns:
            AI响应文本
        """
        messages = [
            {"role": "user", "content": prompt}
        ]
        return await self.chat_completion(messages, temperature, max_tokens, timeout, max_retries)