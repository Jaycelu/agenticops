"""
配置自动化策略脚本

为基地配置自动化策略，使诊断结果能够触发自动化动作。

策略规则说明：
1. 策略匹配逻辑：根据诊断结果的diagnosis_type匹配策略的trigger_condition.diagnosis_type
2. 支持的动作类型：
   - notification: 发送通知（钉钉、邮件等）
   - script: 执行脚本
   - api: 调用API
3. 风险等级：
   - low: 低风险，自动执行
   - medium: 中等风险，需要确认
   - high: 高风险，需要审批
4. 策略状态：
   - enabled: 启用
   - disabled: 禁用

使用方法：
    python3 config_automation_policies.py
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import SessionLocal
from models.automation import AutomationPolicy, Site
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_policies_for_site(site_code: str):
    """
    为指定基地创建自动化策略

    Args:
        site_code: 基地代码，如 "DEYANG"
    """
    db = SessionLocal()

    try:
        # 查询基地
        site = db.query(Site).filter(Site.site_code == site_code).first()
        if not site:
            logger.error(f"基地不存在: {site_code}")
            return

        logger.info(f"开始为基地 {site.site_name} (ID: {site.id}) 配置自动化策略...")

        # 策略1: 链路质量下降策略
        policy1 = AutomationPolicy(
            policy_code=f"{site_code}_LINK_QUALITY_DEGRADE",
            policy_name=f"{site.site_name}-链路质量下降策略",
            site_id=site.id,
            policy_type="DIAGNOSIS",
            trigger_type="diagnosis_result",
            trigger_condition={
                "diagnosis_type": "LINK_QUALITY_DEGRADE"
            },
            action={
                "type": "notification",
                "config": {
                    "channel": "dingtalk",
                    "template": "abnormal_alert",
                    "message": "检测到链路质量下降，CRC错误持续增长"
                }
            },
            risk_level="medium",
            require_confirm=True,
            enabled=True
        )

        # 策略2: 接口震荡策略
        policy2 = AutomationPolicy(
            policy_code=f"{site_code}_INTERFACE_FLAP",
            policy_name=f"{site.site_name}-接口震荡策略",
            site_id=site.id,
            policy_type="DIAGNOSIS",
            trigger_type="diagnosis_result",
            trigger_condition={
                "diagnosis_type": "INTERFACE_FLAP"
            },
            action={
                "type": "notification",
                "config": {
                    "channel": "dingtalk",
                    "template": "abnormal_alert",
                    "message": "检测到接口频繁震荡"
                }
            },
            risk_level="high",
            require_confirm=True,
            enabled=True
        )

        # 策略3: 邻居不稳定策略
        policy3 = AutomationPolicy(
            policy_code=f"{site_code}_NEIGHBOR_UNSTABLE",
            policy_name=f"{site.site_name}-邻居不稳定策略",
            site_id=site.id,
            policy_type="DIAGNOSIS",
            trigger_type="diagnosis_result",
            trigger_condition={
                "diagnosis_type": "NEIGHBOR_UNSTABLE"
            },
            action={
                "type": "notification",
                "config": {
                    "channel": "dingtalk",
                    "template": "abnormal_alert",
                    "message": "检测到邻居关系不稳定"
                }
            },
            risk_level="medium",
            require_confirm=True,
            enabled=True
        )

        # 策略4: 高错误率策略
        policy4 = AutomationPolicy(
            policy_code=f"{site_code}_HIGH_ERROR_RATE",
            policy_name=f"{site.site_name}-高错误率策略",
            site_id=site.id,
            policy_type="DIAGNOSIS",
            trigger_type="diagnosis_result",
            trigger_condition={
                "diagnosis_type": "HIGH_ERROR_RATE"
            },
            action={
                "type": "notification",
                "config": {
                    "channel": "dingtalk",
                    "template": "abnormal_alert",
                    "message": "检测到错误率过高"
                }
            },
            risk_level="medium",
            require_confirm=True,
            enabled=True
        )

        # 策略5: 综合链路问题策略（高风险）
        policy5 = AutomationPolicy(
            policy_code=f"{site_code}_COMBINED_LINK_ISSUE",
            policy_name=f"{site.site_name}-综合链路问题策略",
            site_id=site.id,
            policy_type="DIAGNOSIS",
            trigger_type="diagnosis_result",
            trigger_condition={
                "diagnosis_type": "COMBINED_LINK_ISSUE"
            },
            action={
                "type": "notification",
                "config": {
                    "channel": "dingtalk",
                    "template": "critical_alert",
                    "message": "检测到综合链路问题（CRC+Flap），需要立即处理"
                }
            },
            risk_level="high",
            require_confirm=True,
            enabled=True
        )

        policies = [policy1, policy2, policy3, policy4, policy5]

        # 检查是否已存在
        for policy in policies:
            existing = db.query(AutomationPolicy).filter(
                AutomationPolicy.policy_code == policy.policy_code
            ).first()

            if existing:
                logger.info(f"策略已存在，跳过: {policy.policy_code}")
                continue

            db.add(policy)
            logger.info(f"创建策略: {policy.policy_code} - {policy.policy_name}")

        db.commit()

        logger.info(f"✓ 成功为基地 {site.site_name} 配置了 {len(policies)} 个自动化策略")

        # 显示配置的策略
        logger.info("\n=== 已配置的策略 ===")
        all_policies = db.query(AutomationPolicy).filter(
            AutomationPolicy.site_id == site.id
        ).all()

        for p in all_policies:
            logger.info(f"  {p.policy_code}")
            logger.info(f"    名称: {p.policy_name}")
            logger.info(f"    触发条件: diagnosis_type = {p.trigger_condition.get('diagnosis_type')}")
            logger.info(f"    动作: {p.action.get('type')} - {p.action.get('config', {}).get('message', 'N/A')}")
            logger.info(f"    风险等级: {p.risk_level}, 需确认: {p.require_confirm}")
            logger.info(f"    状态: {'启用' if p.enabled else '禁用'}")
            logger.info("")

    except Exception as e:
        db.rollback()
        logger.error(f"配置策略失败: {e}", exc_info=True)
        raise
    finally:
        db.close()


def list_all_policies():
    """列出所有策略"""
    db = SessionLocal()

    try:
        policies = db.query(AutomationPolicy).all()

        logger.info(f"=== 所有自动化策略 (共{len(policies)}个) ===\n")

        for p in policies:
            site = db.query(Site).filter(Site.id == p.site_id).first()
            logger.info(f"策略ID: {p.id}")
            logger.info(f"  代码: {p.policy_code}")
            logger.info(f"  名称: {p.policy_name}")
            logger.info(f"  基地: {site.site_code if site else 'N/A'}")
            logger.info(f"  类型: {p.policy_type}, 触发: {p.trigger_type}")
            logger.info(f"  触发条件: {p.trigger_condition}")
            logger.info(f"  动作: {p.action}")
            logger.info(f"  风险等级: {p.risk_level}, 需确认: {p.require_confirm}")
            logger.info(f"  状态: {'启用' if p.enabled else '禁用'}")
            logger.info(f"  创建时间: {p.created_at}")
            logger.info("")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="配置自动化策略")
    parser.add_argument("--site", type=str, default="DEYANG", help="基地代码（默认：DEYANG）")
    parser.add_argument("--list", action="store_true", help="列出所有策略")

    args = parser.parse_args()

    if args.list:
        list_all_policies()
    else:
        create_policies_for_site(args.site)
