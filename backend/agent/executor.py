from typing import Dict, Any
from agent.schemas import ExecutionStep
from mcp.netbox_mcp import NetBoxMCP
from mcp.zabbix_mcp import ZabbixMCP
from mcp.elk_mcp import ELKMCP
from config.logging import logger
from datetime import datetime


class ExecutorAgent:
    def __init__(self):
        self.mcps = {
            "netbox": NetBoxMCP(),
            "zabbix": ZabbixMCP(),
            "elk": ELKMCP()
        }
        self.virtual_tool_handlers = {
            "backup": self._execute_backup,
            "inspection": self._execute_inspection,
            "healthcheck": self._execute_healthcheck
        }

    async def execute_step(self, step: ExecutionStep) -> ExecutionStep:
        tool = step.tool
        action = step.action
        params = step.params

        step.status = "running"
        step.start_time = datetime.now()

        try:
            if tool in self.virtual_tool_handlers:
                step.status = "completed"
                step.result = self.virtual_tool_handlers[tool](step)
                step.end_time = datetime.now()
                return step

            if tool not in self.mcps:
                raise Exception(f"Tool {tool} not available")

            mcp = self.mcps[tool]
            result = await mcp.execute(params)

            if result.success:
                step.status = "completed"
                # 将 result.data 和 result.metadata 都存储到 step.result 中
                step.result = {
                    "data": result.data,
                    "metadata": result.metadata
                }
            else:
                step.status = "failed"
                step.error = result.error

        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            logger.error(f"Execution error: {str(e)}")

        step.end_time = datetime.now()
        return step

    def _execute_backup(self, step: ExecutionStep) -> Dict[str, Any]:
        credentials = step.params.get("credentials", {})
        username = credentials.get("username")
        password = credentials.get("password")

        if username == "需要用户提供" or password == "需要用户提供":
            return {
                "status": "pending_input",
                "message": "备份任务已生成，请补充设备登录凭据后执行。",
                "requires_user_input": True,
                "required_fields": ["username", "password"]
            }

        return {
            "status": "queued",
            "message": "备份任务已入队。",
            "filters": step.params.get("filters", {})
        }

    def _execute_inspection(self, step: ExecutionStep) -> Dict[str, Any]:
        credentials = step.params.get("credentials", {})
        username = credentials.get("username")
        password = credentials.get("password")

        if username == "需要用户提供" or password == "需要用户提供":
            return {
                "status": "pending_input",
                "message": "巡检任务已生成，请补充设备登录凭据后执行。",
                "requires_user_input": True,
                "required_fields": ["username", "password"]
            }

        return {
            "status": "queued",
            "message": "巡检任务已入队。",
            "template_id": step.params.get("template_id")
        }

    def _execute_healthcheck(self, step: ExecutionStep) -> Dict[str, Any]:
        return {
            "status": "queued",
            "message": "健康检查任务已入队。",
            "filters": step.params.get("filters", {}),
            "site": step.params.get("site")
        }
