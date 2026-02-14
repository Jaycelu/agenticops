"""
确认服务 - 管理高危操作确认机制
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import SessionLocal
from models.automation import AutomationTask, AutomationPolicy
from services.schemas import SeverityLevel
from services.execution_engine import ExecutorType

logger = logging.getLogger(__name__)


class HighRiskOperationType(str):
    """高危操作类型"""
    DEVICE_REBOOT = "device_reboot"
    CONFIG_CHANGE = "config_change"
    INTERFACE_SHUTDOWN = "interface_shutdown"
    ROUTE_CHANGE = "route_change"
    ACL_CHANGE = "acl_change"
    SERVICE_RESTART = "service_restart"
    DATA_DELETION = "data_deletion"
    SCALE_DOWN = "scale_down"
    NETWORK_ISOLATION = "network_isolation"


class ConfirmationService:
    """确认服务"""

    # 高危操作配置
    HIGH_RISK_OPERATIONS = {
        HighRiskOperationType.DEVICE_REBOOT: {
            "name": "设备重启",
            "risk_level": SeverityLevel.HIGH,
            "description": "重启网络设备可能导致短暂服务中断",
            "auto_confirm": False
        },
        HighRiskOperationType.CONFIG_CHANGE: {
            "name": "配置变更",
            "risk_level": SeverityLevel.MEDIUM,
            "description": "修改设备配置可能影响网络连通性",
            "auto_confirm": False
        },
        HighRiskOperationType.INTERFACE_SHUTDOWN: {
            "name": "接口关闭",
            "risk_level": SeverityLevel.HIGH,
            "description": "关闭接口将导致该接口上的流量中断",
            "auto_confirm": False
        },
        HighRiskOperationType.ROUTE_CHANGE: {
            "name": "路由变更",
            "risk_level": SeverityLevel.HIGH,
            "description": "修改路由可能导致流量路径改变或中断",
            "auto_confirm": False
        },
        HighRiskOperationType.ACL_CHANGE: {
            "name": "ACL变更",
            "risk_level": SeverityLevel.HIGH,
            "description": "修改访问控制列表可能影响网络访问",
            "auto_confirm": False
        },
        HighRiskOperationType.SERVICE_RESTART: {
            "name": "服务重启",
            "risk_level": SeverityLevel.MEDIUM,
            "description": "重启服务可能导致短暂服务不可用",
            "auto_confirm": False
        },
        HighRiskOperationType.DATA_DELETION: {
            "name": "数据删除",
            "risk_level": SeverityLevel.CRITICAL,
            "description": "删除数据操作不可恢复，请谨慎操作",
            "auto_confirm": False
        },
        HighRiskOperationType.SCALE_DOWN: {
            "name": "资源缩减",
            "risk_level": SeverityLevel.MEDIUM,
            "description": "缩减资源可能影响系统性能",
            "auto_confirm": False
        },
        HighRiskOperationType.NETWORK_ISOLATION: {
            "name": "网络隔离",
            "risk_level": SeverityLevel.CRITICAL,
            "description": "隔离网络将导致设备完全不可达",
            "auto_confirm": False
        }
    }

    def __init__(self):
        """初始化确认服务"""
        # 自动确认的配置（根据风险等级）
        self.auto_confirm_threshold = SeverityLevel.LOW

    def is_high_risk_operation(
        self,
        action_type: ExecutorType,
        action_config: Dict[str, Any]
    ) -> tuple[bool, Optional[str], Optional[SeverityLevel]]:
        """
        判断是否为高危操作

        Args:
            action_type: 动作类型
            action_config: 动作配置

        Returns:
            (是否高危, 操作类型, 风险等级)
        """
        # 检查脚本执行器
        if action_type == ExecutorType.SCRIPT:
            script_content = action_config.get("script", "")
            script_type = action_config.get("script_type", "")

            # 检查脚本内容中的高危关键词
            high_risk_keywords = {
                "reboot": HighRiskOperationType.DEVICE_REBOOT,
                "reload": HighRiskOperationType.DEVICE_REBOOT,
                "shutdown": HighRiskOperationType.INTERFACE_SHUTDOWN,
                "no shutdown": HighRiskOperationType.CONFIG_CHANGE,
                "delete": HighRiskOperationType.DATA_DELETION,
                "erase": HighRiskOperationType.DATA_DELETION,
                "format": HighRiskOperationType.DATA_DELETION,
                "route": HighRiskOperationType.ROUTE_CHANGE,
                "ip route": HighRiskOperationType.ROUTE_CHANGE,
                "access-list": HighRiskOperationType.ACL_CHANGE,
                "acl": HighRiskOperationType.ACL_CHANGE,
                "service restart": HighRiskOperationType.SERVICE_RESTART,
                "systemctl restart": HighRiskOperationType.SERVICE_RESTART,
                "isolate": HighRiskOperationType.NETWORK_ISOLATION,
            }

            script_lower = script_content.lower()
            for keyword, operation_type in high_risk_keywords.items():
                if keyword in script_lower:
                    operation_info = self.HIGH_RISK_OPERATIONS.get(operation_type)
                    if operation_info:
                        return True, operation_type, operation_info["risk_level"]

        # 检查API执行器
        elif action_type == ExecutorType.API:
            method = action_config.get("method", "").upper()
            url = action_config.get("url", "")

            # DELETE 方法通常被认为是高危操作
            if method == "DELETE":
                return True, HighRiskOperationType.DATA_DELETION, SeverityLevel.HIGH

            # 检查URL中的高危路径
            high_risk_paths = {
                "/reboot": HighRiskOperationType.DEVICE_REBOOT,
                "/shutdown": HighRiskOperationType.INTERFACE_SHUTDOWN,
                "/restart": HighRiskOperationType.SERVICE_RESTART,
                "/delete": HighRiskOperationType.DATA_DELETION,
                "/remove": HighRiskOperationType.DATA_DELETION,
                "/isolate": HighRiskOperationType.NETWORK_ISOLATION,
            }

            url_lower = url.lower()
            for path, operation_type in high_risk_paths.items():
                if path in url_lower:
                    operation_info = self.HIGH_RISK_OPERATIONS.get(operation_type)
                    if operation_info:
                        return True, operation_type, operation_info["risk_level"]

        return False, None, None

    def requires_confirmation(
        self,
        task_id: int,
        action_type: ExecutorType,
        action_config: Dict[str, Any],
        diagnosis_risk_level: Optional[SeverityLevel] = None
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        判断是否需要确认

        Args:
            task_id: 任务ID
            action_type: 动作类型
            action_config: 动作配置
            diagnosis_risk_level: 诊断风险等级

        Returns:
            (是否需要确认, 原因, 确认信息)
        """
        is_high_risk, operation_type, risk_level = self.is_high_risk_operation(action_type, action_config)

        # 如果是高危操作，需要确认
        if is_high_risk:
            operation_info = self.HIGH_RISK_OPERATIONS.get(operation_type)
            if operation_info:
                return True, f"检测到高危操作：{operation_info['name']}", {
                    "operation_type": operation_type,
                    "operation_name": operation_info["name"],
                    "risk_level": risk_level.value,
                    "description": operation_info["description"]
                }

        # 如果诊断结果要求人工确认
        if diagnosis_risk_level and diagnosis_risk_level in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
            return True, f"诊断结果风险等级为{diagnosis_risk_level.value}，需要人工确认", {
                "operation_type": "diagnosis",
                "operation_name": "诊断确认",
                "risk_level": diagnosis_risk_level.value,
                "description": f"诊断结果风险等级为{diagnosis_risk_level.value}"
            }

        # 检查策略配置
        policy_id = action_config.get("policy_id")
        if policy_id:
            db = SessionLocal()
            try:
                policy = db.query(AutomationPolicy).filter(
                    AutomationPolicy.id == policy_id
                ).first()

                if policy and policy.require_confirm:
                    return True, f"策略 '{policy.policy_name}' 要求执行前确认", {
                        "operation_type": "policy",
                        "operation_name": "策略确认",
                        "risk_level": policy.risk_level,
                        "description": f"策略 '{policy.policy_name}' 配置了执行前确认"
                    }
            finally:
                db.close()

        return False, None, None

    async def request_confirmation(
        self,
        task_id: int,
        confirmation_info: Dict[str, Any]
    ) -> bool:
        """
        请求确认

        Args:
            task_id: 任务ID
            confirmation_info: 确认信息

        Returns:
            是否成功请求确认
        """
        db = SessionLocal()

        try:
            task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return False

            # 更新任务状态为等待确认
            task.status = "waiting_confirm"
            task.need_human_confirm = True
            task.updated_at = datetime.now()

            db.commit()
            db.refresh(task)

            logger.info(f"Task {task_id} status updated to waiting_confirm")

            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error requesting confirmation for task {task_id}: {e}", exc_info=True)
            return False
        finally:
            db.close()

    async def confirm_task(
        self,
        task_id: int,
        user: str,
        approved: bool,
        comment: Optional[str] = None
    ) -> bool:
        """
        确认任务

        Args:
            task_id: 任务ID
            user: 确认用户
            approved: 是否批准
            comment: 评论

        Returns:
            是否成功确认
        """
        db = SessionLocal()

        try:
            task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return False

            if task.status != "waiting_confirm":
                logger.warning(f"Task {task_id} is not in waiting_confirm status")
                return False

            # 记录审批记录
            from models.automation import AutomationApproval
            approval = AutomationApproval(
                task_id=task_id,
                approver=user,
                decision="approved" if approved else "rejected",
                comment=comment
            )
            db.add(approval)

            # 更新任务状态
            if approved:
                task.status = "pending"  # 回到待执行状态
            else:
                task.status = "aborted"  # 拒绝则中止任务

            task.updated_at = datetime.now()

            db.commit()
            db.refresh(task)

            logger.info(f"Task {task_id} confirmed by {user}: {'approved' if approved else 'rejected'}")

            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error confirming task {task_id}: {e}", exc_info=True)
            return False
        finally:
            db.close()

    async def get_pending_confirmations(
        self,
        site_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取待确认的任务列表

        Args:
            site_id: 基地ID（可选）
            limit: 限制数量

        Returns:
            待确认任务列表
        """
        db = SessionLocal()

        try:
            query = db.query(AutomationTask).filter(
                AutomationTask.status == "waiting_confirm"
            )

            if site_id:
                query = query.filter(AutomationTask.site_id == site_id)

            tasks = query.order_by(AutomationTask.created_at.asc()).limit(limit).all()

            result = []
            for task in tasks:
                result.append({
                    "task_id": task.id,
                    "task_code": task.task_code,
                    "site_id": task.site_id,
                    "netbox_device_id": task.netbox_device_id,
                    "triggered_by": task.triggered_by,
                    "decision_result": task.decision_result,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "started_at": task.started_at.isoformat() if task.started_at else None
                })

            return result

        except Exception as e:
            logger.error(f"Error getting pending confirmations: {e}", exc_info=True)
            return []
        finally:
            db.close()

    def get_operation_info(self, operation_type: str) -> Optional[Dict[str, Any]]:
        """
        获取操作信息

        Args:
            operation_type: 操作类型

        Returns:
            操作信息
        """
        return self.HIGH_RISK_OPERATIONS.get(operation_type)


# 全局确认服务实例
confirmation_service = ConfirmationService()