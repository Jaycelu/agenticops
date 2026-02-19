"""
审批服务 - 管理自动化任务审批流程
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from enum import Enum

from database import SessionLocal
from models.automation import AutomationTask, AutomationApproval, AutomationPolicy

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """审批状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalLevel(str, Enum):
    """审批级别"""
    LEVEL_1 = "level_1"  # 一级审批
    LEVEL_2 = "level_2"  # 二级审批
    LEVEL_3 = "level_3"  # 三级审批


class ApprovalFlowConfig:
    """审批流程配置"""

    # 风险等级对应的审批级别
    RISK_LEVEL_TO_APPROVAL = {
        "low": None,  # 低风险不需要审批
        "medium": ApprovalLevel.LEVEL_1,  # 中风险需要一级审批
        "high": ApprovalLevel.LEVEL_2,  # 高风险需要二级审批
        "critical": ApprovalLevel.LEVEL_3  # 严重风险需要三级审批
    }

    # 审批级别对应的审批人配置（示例，实际应从配置或数据库读取）
    APPROVAL_LEVEL_CONFIG = {
        ApprovalLevel.LEVEL_1: {
            "required_approvers": 1,  # 需要1人审批
            "timeout_minutes": 60,  # 60分钟超时
            "description": "一级审批 - 需要运维工程师审批"
        },
        ApprovalLevel.LEVEL_2: {
            "required_approvers": 1,  # 需要1人审批
            "timeout_minutes": 120,  # 120分钟超时
            "description": "二级审批 - 需要运维主管审批"
        },
        ApprovalLevel.LEVEL_3: {
            "required_approvers": 2,  # 需要2人审批
            "timeout_minutes": 240,  # 240分钟超时
            "description": "三级审批 - 需要技术总监和运维总监审批"
        }
    }


class ApprovalService:
    """审批服务"""

    def __init__(self):
        """初始化审批服务"""
        self.flow_config = ApprovalFlowConfig()

    @staticmethod
    def _get_db(db: Optional[Session] = None):
        if db is not None:
            return db, False
        return SessionLocal(), True

    def get_approval_level(self, risk_level: str) -> Optional[ApprovalLevel]:
        """
        根据风险等级获取审批级别

        Args:
            risk_level: 风险等级

        Returns:
            审批级别
        """
        return self.flow_config.RISK_LEVEL_TO_APPROVAL.get(risk_level)

    def get_required_approvers(self, approval_level: ApprovalLevel) -> int:
        """
        获取需要的审批人数

        Args:
            approval_level: 审批级别

        Returns:
            需要的审批人数
        """
        config = self.flow_config.APPROVAL_LEVEL_CONFIG.get(approval_level)
        return config["required_approvers"] if config else 0

    def get_approval_timeout(self, approval_level: ApprovalLevel) -> int:
        """
        获取审批超时时间（分钟）

        Args:
            approval_level: 审批级别

        Returns:
            超时时间（分钟）
        """
        config = self.flow_config.APPROVAL_LEVEL_CONFIG.get(approval_level)
        return config["timeout_minutes"] if config else 0

    async def initiate_approval(
        self,
        task_id: int,
        risk_level: str,
        initiator: str,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        发起审批流程

        Args:
            task_id: 任务ID
            risk_level: 风险等级
            initiator: 发起人

        Returns:
            审批流程信息
        """
        db, own_db = self._get_db(db)

        try:
            task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return {"success": False, "message": "Task not found"}

            if task.status not in {"waiting_confirm", "pending"}:
                return {"success": False, "message": f"Task status {task.status} cannot initiate approval"}

            # 获取审批级别
            approval_level = self.get_approval_level(risk_level)
            if not approval_level:
                logger.info(f"Task {task_id} with risk level {risk_level} does not require approval")
                return {"success": True, "message": "No approval required", "approval_level": None}

            # 更新任务状态
            task.status = "waiting_approval"
            task.need_human_confirm = True
            task.updated_at = datetime.now()
            trail = task.audit_trail or []
            trail.append(
                {
                    "stage": "Approval",
                    "title": "发起审批",
                    "payload": {
                        "initiator": initiator,
                        "risk_level": risk_level,
                        "approval_level": approval_level.value,
                    },
                }
            )
            task.audit_trail = trail

            db.commit()
            db.refresh(task)

            # 获取审批配置
            required_approvers = self.get_required_approvers(approval_level)
            timeout_minutes = self.get_approval_timeout(approval_level)

            approval_info = {
                "task_id": task_id,
                "task_code": task.task_code,
                "approval_level": approval_level.value,
                "required_approvers": required_approvers,
                "timeout_minutes": timeout_minutes,
                "initiator": initiator,
                "status": ApprovalStatus.PENDING.value,
                "created_at": datetime.now().isoformat()
            }

            logger.info(f"Approval initiated for task {task_id}: {approval_info}")

            return {"success": True, "approval": approval_info}

        except Exception as e:
            db.rollback()
            logger.error(f"Error initiating approval for task {task_id}: {e}", exc_info=True)
            return {"success": False, "message": str(e)}
        finally:
            if own_db:
                db.close()

    async def approve_task(
        self,
        task_id: int,
        approver: str,
        decision: str,
        comment: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        审批任务

        Args:
            task_id: 任务ID
            approver: 审批人
            decision: 决策（approved/rejected）
            comment: 评论

        Returns:
            审批结果
        """
        db, own_db = self._get_db(db)

        try:
            task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return {"success": False, "message": "Task not found"}

            if task.status != "waiting_approval":
                logger.warning(f"Task {task_id} is not in waiting_approval status")
                return {"success": False, "message": "Task is not waiting for approval"}

            decision = (decision or "").strip().lower()
            if decision not in {"approved", "rejected"}:
                return {"success": False, "message": "decision must be approved|rejected"}

            duplicate = db.query(AutomationApproval).filter(
                AutomationApproval.task_id == task_id,
                AutomationApproval.approver == approver
            ).first()
            if duplicate:
                return {"success": False, "message": "approver has already submitted decision"}

            # 记录审批记录
            approval = AutomationApproval(
                task_id=task_id,
                approver=approver,
                decision=decision,
                comment=comment
            )
            db.add(approval)

            # 获取现有的审批记录
            existing_approvals = db.query(AutomationApproval).filter(
                AutomationApproval.task_id == task_id,
                AutomationApproval.decision == "approved"
            ).count()

            # 获取需要的审批人数
            risk_level = task.decision_result.get("diagnosis", {}).get("risk_level", "medium") if task.decision_result else "medium"
            approval_level = self.get_approval_level(risk_level)
            required_approvers = self.get_required_approvers(approval_level) if approval_level else 0

            # 判断审批是否完成
            if decision == "rejected":
                # 拒绝则中止任务
                task.status = "aborted"
                logger.info(f"Task {task_id} rejected by {approver}")
            elif existing_approvals + 1 >= required_approvers:
                # 审批通过，回到待执行状态
                task.status = "pending"
                task.need_human_confirm = False
                logger.info(f"Task {task_id} approved by {approver}")
            else:
                # 还需要更多审批人
                logger.info(f"Task {task_id} approved by {approver}, waiting for more approvers")

            task.updated_at = datetime.now()
            trail = task.audit_trail or []
            trail.append(
                {
                    "stage": "Approval",
                    "title": "审批决策",
                    "payload": {
                        "approver": approver,
                        "decision": decision,
                        "comment": comment or "",
                        "result_status": task.status,
                    },
                }
            )
            task.audit_trail = trail
            db.commit()
            db.refresh(task)

            return {
                "success": True,
                "task_id": task_id,
                "status": task.status,
                "approver": approver,
                "decision": decision,
                "remaining_approvals": max(0, required_approvers - existing_approvals - 1)
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error approving task {task_id}: {e}", exc_info=True)
            return {"success": False, "message": str(e)}
        finally:
            if own_db:
                db.close()

    async def get_approval_history(
        self,
        task_id: int,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取审批历史

        Args:
            task_id: 任务ID

        Returns:
            审批历史列表
        """
        db, own_db = self._get_db(db)

        try:
            approvals = db.query(AutomationApproval).filter(
                AutomationApproval.task_id == task_id
            ).order_by(AutomationApproval.created_at.asc()).all()

            result = []
            for approval in approvals:
                result.append({
                    "approval_id": approval.id,
                    "approver": approval.approver,
                    "decision": approval.decision,
                    "comment": approval.comment,
                    "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
                    "created_at": approval.created_at.isoformat() if approval.created_at else None
                })

            return result

        except Exception as e:
            logger.error(f"Error getting approval history for task {task_id}: {e}", exc_info=True)
            return []
        finally:
            if own_db:
                db.close()

    async def get_pending_approvals(
        self,
        site_id: Optional[int] = None,
        approver: Optional[str] = None,
        limit: int = 100,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取待审批的任务列表

        Args:
            site_id: 基地ID（可选）
            approver: 审批人（可选）
            limit: 限制数量

        Returns:
            待审批任务列表
        """
        db, own_db = self._get_db(db)

        try:
            query = db.query(AutomationTask).filter(
                AutomationTask.status == "waiting_approval"
            )

            if site_id:
                query = query.filter(AutomationTask.site_id == site_id)

            tasks = query.order_by(AutomationTask.created_at.asc()).limit(limit).all()

            result = []
            for task in tasks:
                # 获取审批历史
                approvals = await self.get_approval_history(task.id, db=db)

                # 获取风险等级
                risk_level = task.decision_result.get("diagnosis", {}).get("risk_level", "medium") if task.decision_result else "medium"
                approval_level = self.get_approval_level(risk_level)
                required_approvers = self.get_required_approvers(approval_level) if approval_level else 0
                approved_count = sum(1 for a in approvals if a["decision"] == "approved")

                result.append({
                    "task_id": task.id,
                    "task_code": task.task_code,
                    "site_id": task.site_id,
                    "netbox_device_id": task.netbox_device_id,
                    "triggered_by": task.triggered_by,
                    "risk_level": risk_level,
                    "approval_level": approval_level.value if approval_level else None,
                    "required_approvers": required_approvers,
                    "approved_count": approved_count,
                    "decision_result": task.decision_result,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "started_at": task.started_at.isoformat() if task.started_at else None
                })

            return result

        except Exception as e:
            logger.error(f"Error getting pending approvals: {e}", exc_info=True)
            return []
        finally:
            if own_db:
                db.close()

    async def cancel_approval(
        self,
        task_id: int,
        user: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        取消审批

        Args:
            task_id: 任务ID
            user: 操作用户
            reason: 取消原因

        Returns:
            是否成功取消
        """
        db = SessionLocal()

        try:
            task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return False

            if task.status != "waiting_approval":
                logger.warning(f"Task {task_id} is not in waiting_approval status")
                return False

            # 更新任务状态
            task.status = "cancelled"
            task.need_human_confirm = False
            task.updated_at = datetime.now()

            db.commit()
            db.refresh(task)

            logger.info(f"Approval cancelled for task {task_id} by {user}: {reason}")

            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error cancelling approval for task {task_id}: {e}", exc_info=True)
            return False
        finally:
            db.close()


# 全局审批服务实例
approval_service = ApprovalService()
