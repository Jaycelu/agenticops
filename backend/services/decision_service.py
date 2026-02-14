"""
决策服务 - 管理决策结果的创建和持久化
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

from database import SessionLocal
from models.automation import (
    AutomationTask, AutomationPolicy, AutomationActionLog,
    LogSample, RawAnomaly
)
from services.schemas import (
    DecisionResult, DiagnosisResult, ExecutionResult, TaskTriggerEvent
)

logger = logging.getLogger(__name__)


class DecisionService:
    """决策服务"""

    async def create_decision_task(
        self,
        site_id: int,
        netbox_device_id: Optional[int],
        device_ip: str,
        decision_result: DecisionResult,
        trigger_event: TaskTriggerEvent,
        policy_id: Optional[int] = None
    ) -> AutomationTask:
        """
        创建决策任务

        Args:
            site_id: 基地ID
            netbox_device_id: NetBox设备ID
            device_ip: 设备IP
            decision_result: 决策结果
            trigger_event: 触发事件
            policy_id: 策略ID（可选）

        Returns:
            创建的自动化任务
        """
        db = SessionLocal()

        try:
            # 生成任务代码
            task_code = f"TASK_{site_id}_{device_ip.replace('.', '_')}_{int(datetime.now().timestamp())}"

            # 确保context中包含device_ip
            decision_dict = decision_result.model_dump()
            if "context" not in decision_dict:
                decision_dict["context"] = {}
            decision_dict["context"]["device_ip"] = device_ip
            decision_dict["context"]["site_id"] = site_id
            if netbox_device_id:
                decision_dict["context"]["netbox_device_id"] = netbox_device_id

            # 创建任务
            task = AutomationTask(
                task_code=task_code,
                policy_id=policy_id,
                site_id=site_id,
                netbox_device_id=netbox_device_id,
                status="pending",
                triggered_by=trigger_event.event_type,
                trigger_event=trigger_event.model_dump(),
                decision_result=decision_dict,
                need_human_confirm=decision_result.diagnosis.require_human_confirm,
                started_at=datetime.now()
            )

            db.add(task)
            db.commit()
            db.refresh(task)

            logger.info(f"Created decision task {task.id} for device {device_ip}")

            # 记录动作日志
            await self._log_action(
                db, task.id, "decision",
                "决策结果生成",
                {"decision": decision_result.model_dump()}
            )

            # 返回task_id而不是task对象，避免DetachedInstanceError
            return task.id

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating decision task: {e}", exc_info=True)
            raise
        finally:
            db.close()
        # 注意：这里不关闭Session，让task对象保持attached状态

    async def update_task_status(
        self,
        task_id: int,
        status: str,
        execution_result: Optional[ExecutionResult] = None
    ) -> Optional[AutomationTask]:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            execution_result: 执行结果（可选）

        Returns:
            更新后的任务
        """
        db = SessionLocal()

        try:
            task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            if not task:
                logger.warning(f"Task {task_id} not found")
                return None

            task.status = status

            if execution_result:
                task.execution_result = execution_result.model_dump()

            if status in ["success", "failed", "aborted"]:
                task.finished_at = datetime.now()

            db.commit()
            db.refresh(task)

            logger.info(f"Updated task {task_id} status to {status}")

            # 记录动作日志
            await self._log_action(
                db, task_id, "status_update",
                f"状态更新为{status}",
                {"status": status, "execution_result": execution_result.model_dump() if execution_result else None}
            )

            return task

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating task status: {e}", exc_info=True)
            raise
        finally:
            db.close()

    async def get_task_by_id(self, task_id: int) -> Optional[AutomationTask]:
        """
        获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象
        """
        db = SessionLocal()

        try:
            task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            return task
        finally:
            db.close()

    async def get_tasks_by_site(
        self,
        site_id: int,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[AutomationTask]:
        """
        获取基地的任务列表

        Args:
            site_id: 基地ID
            status: 状态过滤（可选）
            limit: 限制数量

        Returns:
            任务列表
        """
        db = SessionLocal()

        try:
            query = db.query(AutomationTask).filter(AutomationTask.site_id == site_id)

            if status:
                query = query.filter(AutomationTask.status == status)

            tasks = query.order_by(AutomationTask.created_at.desc()).limit(limit).all()
            return tasks
        finally:
            db.close()

    async def _log_action(
        self,
        db: Session,
        task_id: int,
        action_type: str,
        message: str,
        details: Dict[str, Any]
    ):
        """
        记录动作日志

        Args:
            db: 数据库会话
            task_id: 任务ID
            action_type: 动作类型
            message: 消息
            details: 详情
        """
        try:
            action_log = AutomationActionLog(
                task_id=task_id,
                action_type=action_type,
                executor="system",
                result={"message": message, "details": details},
                executed_at=datetime.now()
            )

            db.add(action_log)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging action: {e}", exc_info=True)
            db.rollback()

    async def get_pending_tasks(self, site_id: Optional[int] = None) -> List[AutomationTask]:
        """
        获取待处理的任务

        Args:
            site_id: 基地ID（可选）

        Returns:
            待处理任务列表
        """
        db = SessionLocal()

        try:
            query = db.query(AutomationTask).filter(
                AutomationTask.status == "pending"
            )

            if site_id:
                query = query.filter(AutomationTask.site_id == site_id)

            tasks = query.order_by(AutomationTask.created_at.asc()).all()
            return tasks
        finally:
            db.close()

    async def get_waiting_confirm_tasks(self, site_id: Optional[int] = None) -> List[AutomationTask]:
        """
        获取等待确认的任务

        Args:
            site_id: 基地ID（可选）

        Returns:
            等待确认任务列表
        """
        db = SessionLocal()

        try:
            query = db.query(AutomationTask).filter(
                AutomationTask.status == "waiting_confirm"
            )

            if site_id:
                query = query.filter(AutomationTask.site_id == site_id)

            tasks = query.order_by(AutomationTask.created_at.asc()).all()
            return tasks
        finally:
            db.close()


# 全局决策服务实例
decision_service = DecisionService()