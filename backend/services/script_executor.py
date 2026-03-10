"""
脚本执行器 - 执行本地脚本或远程命令
"""
import logging
import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional
from services.execution_engine import Executor, ExecutorType, ExecutionStatus, ExecutionResult

logger = logging.getLogger(__name__)


class ScriptExecutor(Executor):
    """脚本执行器"""

    def __init__(self):
        """初始化脚本执行器"""
        super().__init__(ExecutorType.SCRIPT)
        self.script_dir = str(Path(__file__).resolve().parents[2] / "scripts")

    async def execute(
        self,
        task_id: int,
        action_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行脚本

        Args:
            task_id: 任务ID
            action_config: 动作配置
            context: 上下文信息

        Returns:
            执行结果
        """
        script_path = action_config.get("script_path")
        script_args = action_config.get("script_args", [])
        working_dir = action_config.get("working_dir", self.script_dir)
        timeout = action_config.get("timeout", 60)

        if not script_path:
            return {
                "status": "failed",
                "message": "Script path is required",
                "error": "script_path not provided in action_config"
            }

        # 构建完整路径
        if not os.path.isabs(script_path):
            script_path = os.path.join(working_dir, script_path)

        if not os.path.exists(script_path):
            return {
                "status": "failed",
                "message": f"Script not found: {script_path}",
                "error": f"Script file does not exist: {script_path}"
            }

        # 构建命令
        command = [script_path] + script_args

        # 添加上下文参数
        if context:
            for key, value in context.items():
                if isinstance(value, (str, int, float, bool)):
                    command.extend([f"--{key}", str(value)])

        logger.info(f"Executing script for task {task_id}: {' '.join(command)}")

        try:
            # 执行脚本
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "status": "failed",
                    "message": f"Script execution timeout after {timeout}s",
                    "error": "Script execution timed out"
                }

            output = stdout.decode('utf-8', errors='ignore')
            error = stderr.decode('utf-8', errors='ignore')

            if process.returncode == 0:
                return {
                    "status": "success",
                    "message": "Script executed successfully",
                    "details": {
                        "return_code": process.returncode,
                        "command": ' '.join(command)
                    },
                    "output": output
                }
            else:
                return {
                    "status": "failed",
                    "message": f"Script execution failed with return code {process.returncode}",
                    "details": {
                        "return_code": process.returncode,
                        "command": ' '.join(command)
                    },
                    "output": output,
                    "error": error
                }

        except Exception as e:
            logger.error(f"Error executing script for task {task_id}: {e}", exc_info=True)
            return {
                "status": "failed",
                "message": f"Script execution error: {str(e)}",
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
        return "script_path" in action_config

    def description(self) -> str:
        """
        获取执行器描述

        Returns:
            描述文本
        """
        return f"Script executor (scripts directory: {self.script_dir})"


# 全局脚本执行器实例
script_executor = ScriptExecutor()
