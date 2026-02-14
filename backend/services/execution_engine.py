"""
执行引擎 - 自动化执行框架
"""
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutorType(str, Enum):
    """执行器类型"""
    SCRIPT = "script"
    API = "api"
    NOTIFICATION = "notification"


class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"
    RETRYING = "retrying"


class Executor(ABC):
    """执行器基类"""

    def __init__(self, executor_type: ExecutorType):
        """
        初始化执行器

        Args:
            executor_type: 执行器类型
        """
        self.executor_type = executor_type

    @abstractmethod
    async def execute(
        self,
        task_id: int,
        action_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行动作

        Args:
            task_id: 任务ID
            action_config: 动作配置
            context: 上下文信息

        Returns:
            执行结果
        """
        pass

    @abstractmethod
    def validate_config(self, action_config: Dict[str, Any]) -> bool:
        """
        验证动作配置

        Args:
            action_config: 动作配置

        Returns:
            是否有效
        """
        pass

    def description(self) -> str:
        """
        获取执行器描述

        Returns:
            描述文本
        """
        return f"{self.executor_type.value} executor"


class ExecutionResult:
    """执行结果"""

    def __init__(
        self,
        status: ExecutionStatus,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        output: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        初始化执行结果

        Args:
            status: 执行状态
            message: 消息
            details: 详情
            output: 输出
            error: 错误
        """
        self.status = status
        self.message = message
        self.details = details or {}
        self.output = output
        self.error = error
        self.executed_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            字典
        """
        return {
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "output": self.output,
            "error": self.error,
            "executed_at": self.executed_at
        }

    def is_success(self) -> bool:
        """
        是否成功

        Returns:
            是否成功
        """
        return self.status == ExecutionStatus.SUCCESS

    def is_failure(self) -> bool:
        """
        是否失败

        Returns:
            是否失败
        """
        return self.status in [ExecutionStatus.FAILED, ExecutionStatus.ABORTED]


class RetryPolicy:
    """重试策略"""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: int = 5,
        backoff_factor: float = 2.0
    ):
        """
        初始化重试策略

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            backoff_factor: 退避因子
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor

    def should_retry(self, attempt: int, execution_result: ExecutionResult) -> bool:
        """
        判断是否应该重试

        Args:
            attempt: 当前尝试次数
            execution_result: 执行结果

        Returns:
            是否应该重试
        """
        return (
            attempt < self.max_retries
            and execution_result.is_failure()
        )

    def get_retry_delay(self, attempt: int) -> int:
        """
        获取重试延迟

        Args:
            attempt: 当前尝试次数

        Returns:
            重试延迟（秒）
        """
        return int(self.retry_delay * (self.backoff_factor ** attempt))


class ExecutionEngine:
    """执行引擎"""

    def __init__(self):
        """初始化执行引擎"""
        self.executors: Dict[ExecutorType, Executor] = {}
        self.default_retry_policy = RetryPolicy()

    def register_executor(self, executor: Executor):
        """
        注册执行器

        Args:
            executor: 执行器
        """
        self.executors[executor.executor_type] = executor
        logger.info(f"Registered executor: {executor.executor_type.value}")

    async def execute_action(
        self,
        task_id: int,
        action_type: ExecutorType,
        action_config: Dict[str, Any],
        context: Dict[str, Any],
        retry_policy: Optional[RetryPolicy] = None
    ) -> ExecutionResult:
        """
        执行动作

        Args:
            task_id: 任务ID
            action_type: 动作类型
            action_config: 动作配置
            context: 上下文信息
            retry_policy: 重试策略（可选）

        Returns:
            执行结果
        """
        executor = self.executors.get(action_type)
        if not executor:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Executor not found for type: {action_type.value}",
                error=f"No executor registered for {action_type.value}"
            )

        # 验证配置
        if not executor.validate_config(action_config):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message="Invalid action configuration",
                error="Action configuration validation failed"
            )

        # 执行动作（带重试）
        retry_policy = retry_policy or self.default_retry_policy
        last_result = None

        for attempt in range(retry_policy.max_retries + 1):
            try:
                if attempt > 0:
                    delay = retry_policy.get_retry_delay(attempt - 1)
                    logger.info(f"Retrying action for task {task_id} (attempt {attempt + 1}) after {delay}s")
                    import asyncio
                    await asyncio.sleep(delay)

                result_dict = await executor.execute(task_id, action_config, context)
                result = ExecutionResult(
                    status=ExecutionStatus(result_dict.get("status", "failed")),
                    message=result_dict.get("message", ""),
                    details=result_dict.get("details", {}),
                    output=result_dict.get("output"),
                    error=result_dict.get("error")
                )

                if result.is_success() or not retry_policy.should_retry(attempt, result):
                    return result

                last_result = result

            except Exception as e:
                logger.error(f"Error executing action for task {task_id}: {e}", exc_info=True)
                last_result = ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=f"Execution error: {str(e)}",
                    error=str(e)
                )

                if not retry_policy.should_retry(attempt, last_result):
                    return last_result

        return last_result

    def list_executors(self) -> List[str]:
        """
        列出所有执行器

        Returns:
            执行器类型列表
        """
        return [executor_type.value for executor_type in self.executors.keys()]


# 全局执行引擎实例
execution_engine = ExecutionEngine()