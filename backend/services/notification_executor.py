"""
通知执行器 - 发送钉钉通知
"""
import logging
import json
from typing import Dict, Any, Optional
import aiohttp

from services.execution_engine import Executor, ExecutorType, ExecutionResult

logger = logging.getLogger(__name__)


class NotificationExecutor(Executor):
    """通知执行器"""

    def __init__(self):
        """初始化通知执行器"""
        super().__init__(ExecutorType.NOTIFICATION)

    async def execute(
        self,
        task_id: int,
        action_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送通知

        Args:
            task_id: 任务ID
            action_config: 动作配置
            context: 上下文信息

        Returns:
            执行结果
        """
        notification_type = action_config.get("notification_type", "dingtalk")
        webhook_url = action_config.get("webhook_url")
        message = action_config.get("message", "")
        title = action_config.get("title", "自动化通知")
        at_mobiles = action_config.get("at_mobiles", [])
        is_at_all = action_config.get("is_at_all", False)

        if notification_type == "dingtalk":
            return await self._send_dingtalk(
                task_id, webhook_url, title, message, at_mobiles, is_at_all, context
            )
        else:
            return {
                "status": "failed",
                "message": f"Unsupported notification type: {notification_type}",
                "error": f"Notification type {notification_type} not supported"
            }

    async def _send_dingtalk(
        self,
        task_id: int,
        webhook_url: str,
        title: str,
        message: str,
        at_mobiles: list,
        is_at_all: bool,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送钉钉通知

        Args:
            task_id: 任务ID
            webhook_url: Webhook URL
            title: 标题
            message: 消息
            at_mobiles: @的手机号列表
            is_at_all: 是否@所有人
            context: 上下文信息

        Returns:
            执行结果
        """
        if not webhook_url:
            return {
                "status": "failed",
                "message": "Webhook URL is required for DingTalk notification",
                "error": "webhook_url not provided"
            }

        # 构建消息内容
        text_content = f"### {title}\n\n{message}\n"

        # 添加上下文信息
        if context:
            text_content += "\n**详细信息：**\n"
            for key, value in context.items():
                if isinstance(value, (str, int, float, bool)):
                    text_content += f"- {key}: {value}\n"

        # 构建钉钉消息
        dingtalk_message = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text_content
            },
            "at": {
                "atMobiles": at_mobiles,
                "isAtAll": is_at_all
            }
        }

        logger.info(f"Sending DingTalk notification for task {task_id}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=dingtalk_message,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_text = await response.text()

                    try:
                        response_data = await response.json()
                    except:
                        response_data = response_text

                    if response.status == 200 and response_data.get("errcode") == 0:
                        return {
                            "status": "success",
                            "message": "DingTalk notification sent successfully",
                            "details": {
                                "webhook_url": webhook_url,
                                "title": title,
                                "at_mobiles": at_mobiles
                            },
                            "output": response_data
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": f"DingTalk notification failed: {response_data.get('errmsg', 'Unknown error')}",
                            "details": {
                                "webhook_url": webhook_url,
                                "errcode": response_data.get("errcode"),
                                "errmsg": response_data.get("errmsg")
                            },
                            "error": response_data.get("errmsg", "Unknown error")
                        }

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error sending DingTalk notification for task {task_id}: {e}", exc_info=True)
            return {
                "status": "failed",
                "message": f"HTTP client error: {str(e)}",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error sending DingTalk notification for task {task_id}: {e}", exc_info=True)
            return {
                "status": "failed",
                "message": f"Notification error: {str(e)}",
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
        required_fields = ["notification_type", "webhook_url", "message"]
        return all(field in action_config for field in required_fields)

    def description(self) -> str:
        """
        获取执行器描述

        Returns:
            描述文本
        """
        return "Notification executor (DingTalk)"


# 全局通知执行器实例
notification_executor = NotificationExecutor()
