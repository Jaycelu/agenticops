"""
策略匹配引擎 - 匹配自动化策略
"""
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from database import SessionLocal
from models.automation import AutomationPolicy, LogSample, RawAnomaly
from services.rule_engine import RuleParser

logger = logging.getLogger(__name__)


class PolicyMatcher:
    """策略匹配引擎"""

    def __init__(self):
        """初始化策略匹配引擎"""
        pass

    async def match_policies_for_log_sample(
        self,
        log_sample: LogSample,
        db: Optional[Session] = None
    ) -> List[AutomationPolicy]:
        """
        为日志采样匹配策略

        Args:
            log_sample: 日志采样对象
            db: 数据库会话（可选）

        Returns:
            匹配的策略列表
        """
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            # 查询该基地的启用策略
            policies = db.query(AutomationPolicy).filter(
                AutomationPolicy.site_id == log_sample.site_id,
                AutomationPolicy.enabled == True,
                AutomationPolicy.policy_type == "DIAGNOSIS"
            ).all()

            matched_policies = []

            for policy in policies:
                # 检查触发条件
                if await self._evaluate_policy_condition(
                    policy.trigger_condition,
                    log_sample,
                    db
                ):
                    matched_policies.append(policy)
                    logger.info(f"Policy {policy.policy_code} matched for log_sample {log_sample.id}")

            return matched_policies

        except Exception as e:
            logger.error(f"Error matching policies for log_sample: {e}", exc_info=True)
            return []
        finally:
            if should_close:
                db.close()

    async def match_policies_for_raw_anomaly(
        self,
        raw_anomaly: RawAnomaly,
        db: Optional[Session] = None
    ) -> List[AutomationPolicy]:
        """
        为Raw Anomaly匹配策略

        Args:
            raw_anomaly: Raw Anomaly对象
            db: 数据库会话（可选）

        Returns:
            匹配的策略列表
        """
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            # 查询该基地的启用策略
            policies = db.query(AutomationPolicy).filter(
                AutomationPolicy.site_id == raw_anomaly.site_id,
                AutomationPolicy.enabled == True,
                AutomationPolicy.policy_type == "DIAGNOSIS"
            ).all()

            matched_policies = []

            for policy in policies:
                # 检查触发条件
                if await self._evaluate_policy_condition(
                    policy.trigger_condition,
                    raw_anomaly,
                    db
                ):
                    matched_policies.append(policy)
                    logger.info(f"Policy {policy.policy_code} matched for raw_anomaly {raw_anomaly.id}")

            return matched_policies

        except Exception as e:
            logger.error(f"Error matching policies for raw_anomaly: {e}", exc_info=True)
            return []
        finally:
            if should_close:
                db.close()

    async def _evaluate_policy_condition(
        self,
        condition: Dict[str, Any],
        source: Any,
        db: Session
    ) -> bool:
        """
        评估策略条件

        Args:
            condition: 条件字典
            source: 源对象（LogSample或RawAnomaly）
            db: 数据库会话

        Returns:
            是否匹配
        """
        try:
            # 解析条件
            rule_condition = RuleParser.parse_condition(condition)

            # 构建上下文
            context = self._build_context(source, db)

            # 评估条件
            return rule_condition.evaluate(context)

        except Exception as e:
            logger.error(f"Error evaluating policy condition: {e}", exc_info=True)
            return False

    def _build_context(self, source: Any, db: Session) -> Dict[str, Any]:
        """
        构建上下文

        Args:
            source: 源对象
            db: 数据库会话

        Returns:
            上下文字典
        """
        context = {}

        if isinstance(source, LogSample):
            # LogSample上下文
            context.update({
                "site_id": source.site_id,
                "netbox_device_id": source.netbox_device_id,
                "error_count": source.error_count or 0,
                "crc_error_count": source.crc_error_count or 0,
                "flap_count": source.flap_count or 0,
                "neighbor_change_count": source.neighbor_change_count or 0,
                "is_abnormal": source.is_abnormal,
                "abnormal_type": source.abnormal_type
            })

            # 添加原始数据
            if source.raw_data:
                context["device_ip"] = source.raw_data.get("device_ip")
                context["log_messages"] = source.raw_data.get("log_messages", [])

        elif isinstance(source, RawAnomaly):
            # RawAnomaly上下文
            context.update({
                "site_id": source.site_id,
                "device_id": source.device_id,
                "device_ip": source.device_ip,
                "log_fingerprint": source.log_fingerprint,
                "log_count": source.log_count,
                "baseline_avg_5m": float(source.baseline_avg_5m) if source.baseline_avg_5m else None,
                "baseline_p95_5m": float(source.baseline_p95_5m) if source.baseline_p95_5m else None,
                "baseline_count_7d": source.baseline_count_7d or 0,
                "deviation_ratio": float(source.deviation_ratio) if source.deviation_ratio else None
            })

            # 添加日志消息
            if source.log_samples:
                context["log_messages"] = source.log_samples.get("messages", [])

        return context

    async def get_policy_by_code(self, policy_code: str, db: Optional[Session] = None) -> Optional[AutomationPolicy]:
        """
        根据代码获取策略

        Args:
            policy_code: 策略代码
            db: 数据库会话（可选）

        Returns:
            策略对象
        """
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            policy = db.query(AutomationPolicy).filter(
                AutomationPolicy.policy_code == policy_code
            ).first()
            return policy
        finally:
            if should_close:
                db.close()

    async def get_enabled_policies(
        self,
        site_id: int,
        policy_type: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[AutomationPolicy]:
        """
        获取启用的策略

        Args:
            site_id: 基地ID
            policy_type: 策略类型（可选）
            db: 数据库会话（可选）

        Returns:
            策略列表
        """
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            query = db.query(AutomationPolicy).filter(
                AutomationPolicy.site_id == site_id,
                AutomationPolicy.enabled == True
            )

            if policy_type:
                query = query.filter(AutomationPolicy.policy_type == policy_type)

            policies = query.all()
            return policies
        finally:
            if should_close:
                db.close()


# 全局策略匹配引擎实例
policy_matcher = PolicyMatcher()