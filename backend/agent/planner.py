from typing import List, Optional
from agent.schemas import Intent, ExecutionStep, ExecutionPlan
from utils.idgen import generate_id
from datetime import datetime


class PlannerAgent:
    def __init__(self):
        pass

    async def build_plan(self, intent: Intent) -> ExecutionPlan:
        steps = []

        # 自动化任务
        if intent.automation_type == "backup_config":
            steps.extend(self._build_backup_steps(intent))
        elif intent.automation_type == "inspection":
            steps.extend(self._build_inspection_steps(intent))
        elif intent.automation_type == "health_check":
            steps.extend(self._build_health_check_steps(intent))
        else:
            # 查询类任务
            if "netbox" in intent.tools:
                steps.extend(self._build_netbox_steps(intent))

            if "zabbix" in intent.tools:
                steps.extend(self._build_zabbix_steps(intent))

            if "elk" in intent.tools:
                steps.extend(self._build_elk_steps(intent))

        plan = ExecutionPlan(
            plan_id=generate_id("plan"),
            intent=intent,
            steps=steps
        )

        return plan

    def _build_netbox_steps(self, intent: Intent) -> List[ExecutionStep]:
        steps = []

        if intent.intent == "query_device":
            params = {"action": "query_devices"}
            if intent.targets:
                params["name"] = intent.targets[0]
            if intent.role:
                params["role"] = intent.role
            if intent.site:
                params["site"] = intent.site

            steps.append(ExecutionStep(
                step_id=generate_id("step"),
                tool="netbox",
                action="query_devices",
                params=params,
                status="pending"
            ))

        return steps

    def _build_zabbix_steps(self, intent: Intent) -> List[ExecutionStep]:
        steps = []

        if intent.intent == "analyze_device":
            params = {"action": "query_alerts"}
            if intent.targets:
                params["host"] = intent.targets[0]

            steps.append(ExecutionStep(
                step_id=generate_id("step"),
                tool="zabbix",
                action="query_alerts",
                params=params,
                status="pending"
            ))

        return steps

    def _build_elk_steps(self, intent: Intent) -> List[ExecutionStep]:
        steps = []

        if intent.intent == "analyze_device":
            params = {"action": "query_logs"}
            if intent.targets:
                params["query"] = intent.targets[0]
            if intent.time_range:
                params["time_range"] = intent.time_range

            steps.append(ExecutionStep(
                step_id=generate_id("step"),
                tool="elk",
                action="query_logs",
                params=params,
                status="pending"
            ))

        return steps

    def _build_backup_steps(self, intent: Intent) -> List[ExecutionStep]:
        """构建配置备份步骤"""
        steps = []

        # 第一步：从NetBox查询设备列表
        netbox_params = {"action": "query_devices"}
        if intent.targets:
            netbox_params["name"] = intent.targets[0]
        if intent.role:
            netbox_params["role"] = intent.role
        if intent.site:
            netbox_params["site"] = intent.site

        steps.append(ExecutionStep(
            step_id=generate_id("step"),
            tool="netbox",
            action="query_devices",
            params=netbox_params,
            status="pending"
        ))

        # 第二步：执行备份（需要用户确认）
        steps.append(ExecutionStep(
            step_id=generate_id("step"),
            tool="backup",
            action="backup_from_netbox",
            params={
                "filters": netbox_params,
                "credentials": {
                    "username": "需要用户提供",
                    "password": "需要用户提供",
                    "backup_type": intent.backup_type or "full"
                }
            },
            status="pending",
            metadata={"needs_confirmation": True}
        ))

        return steps

    def _build_inspection_steps(self, intent: Intent) -> List[ExecutionStep]:
        """构建巡检步骤"""
        steps = []

        # 第一步：从NetBox查询设备列表
        netbox_params = {"action": "query_devices"}
        if intent.targets:
            netbox_params["name"] = intent.targets[0]
        if intent.role:
            netbox_params["role"] = intent.role
        if intent.site:
            netbox_params["site"] = intent.site

        steps.append(ExecutionStep(
            step_id=generate_id("step"),
            tool="netbox",
            action="query_devices",
            params=netbox_params,
            status="pending"
        ))

        # 第二步：执行巡检
        template_id = intent.inspection_template or self._get_default_template(intent.role)

        steps.append(ExecutionStep(
            step_id=generate_id("step"),
            tool="inspection",
            action="execute_inspection_from_netbox",
            params={
                "template_id": template_id,
                "filters": netbox_params,
                "credentials": {
                    "username": "需要用户提供",
                    "password": "需要用户提供"
                },
                "report_format": "html"
            },
            status="pending"
        ))

        return steps

    def _build_health_check_steps(self, intent: Intent) -> List[ExecutionStep]:
        """构建健康度检查步骤"""
        steps = []

        # 第一步：从NetBox查询设备列表
        netbox_params = {"action": "query_devices"}
        if intent.targets:
            netbox_params["name"] = intent.targets[0]
        if intent.role:
            netbox_params["role"] = intent.role
        if intent.site:
            netbox_params["site"] = intent.site

        steps.append(ExecutionStep(
            step_id=generate_id("step"),
            tool="netbox",
            action="query_devices",
            params=netbox_params,
            status="pending"
        ))

        # 第二步：从Zabbix获取监控数据
        steps.append(ExecutionStep(
            step_id=generate_id("step"),
            tool="zabbix",
            action="query_alerts",
            params={"limit": 1000},
            status="pending"
        ))

        # 第三步：执行健康度检查
        steps.append(ExecutionStep(
            step_id=generate_id("step"),
            tool="healthcheck",
            action="check_network_health_from_mcp",
            params={
                "filters": netbox_params,
                "site": intent.site,
                "report_format": "html"
            },
            status="pending"
        ))

        return steps

    def _get_default_template(self, role: Optional[str]) -> str:
        """根据设备角色获取默认巡检模板"""
        if not role:
            return "access_switch_template"

        role_lower = role.lower()
        if "核心" in role_lower or "core" in role_lower:
            return "core_switch_template"
        elif "防火墙" in role_lower or "firewall" in role_lower:
            return "firewall_template"
        else:
            return "access_switch_template"
