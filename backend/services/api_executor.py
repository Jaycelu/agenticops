"""
API执行器 - 执行HTTP API调用
"""
import logging
import json
import asyncio
from typing import Dict, Any, Optional
import aiohttp

from services.execution_engine import Executor, ExecutorType, ExecutionResult

logger = logging.getLogger(__name__)


class APIExecutor(Executor):
    """API执行器"""

    def __init__(self):
        """初始化API执行器"""
        super().__init__(ExecutorType.API)

    async def execute(
        self,
        task_id: int,
        action_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行API调用

        Args:
            task_id: 任务ID
            action_config: 动作配置
            context: 上下文信息

        Returns:
            执行结果
        """
        url = action_config.get("url")
        method = action_config.get("method", "GET").upper()
        headers = action_config.get("headers", {})
        params = action_config.get("params", {})
        body = action_config.get("body", {})
        timeout = action_config.get("timeout", 30)

        if not url:
            return {
                "status": "failed",
                "message": "URL is required",
                "error": "url not provided in action_config"
            }

        # 合并上下文参数
        if context:
            if method in ["GET", "DELETE"]:
                # 只添加字符串、整数或浮点数的参数
                for key, value in context.items():
                    if isinstance(value, (str, int, float)):
                        params[key] = value
            else:
                body.update(context)

        logger.info(f"Executing API call for task {task_id}: {method} {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body if method in ["POST", "PUT", "PATCH"] else None,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response_text = await response.text()
                    response_data = None

                    try:
                        response_data = await response.json()
                    except:
                        response_data = response_text

                    if 200 <= response.status < 300:
                        return {
                            "status": "success",
                            "message": f"API call successful (status: {response.status})",
                            "details": {
                                "status_code": response.status,
                                "url": url,
                                "method": method
                            },
                            "output": response_data
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": f"API call failed (status: {response.status})",
                            "details": {
                                "status_code": response.status,
                                "url": url,
                                "method": method
                            },
                            "output": response_data,
                            "error": f"HTTP {response.status}"
                        }

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error for task {task_id}: {e}", exc_info=True)
            return {
                "status": "failed",
                "message": f"HTTP client error: {str(e)}",
                "error": str(e)
            }
        except asyncio.TimeoutError:
            logger.error(f"Timeout for task {task_id}")
            return {
                "status": "failed",
                "message": f"API call timeout after {timeout}s",
                "error": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error executing API call for task {task_id}: {e}", exc_info=True)
            return {
                "status": "failed",
                "message": f"API execution error: {str(e)}",
                "error": str(e)
            }

    def validate_config(self, action_config: Dict[str, Any]) -> bool:
        """
        验证动作配置

        Args:
            action_config: 动作配置

        Returns:
            是否有效
        """
        return "url" in action_config and "method" in action_config

    def description(self) -> str:
        """
        获取执行器描述

        Returns:
            描述文本
        """
        return "API executor (HTTP/HTTPS)"


# 全局API执行器实例
api_executor = APIExecutor()