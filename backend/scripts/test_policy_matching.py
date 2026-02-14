"""
测试策略匹配脚本

验证自动化策略是否能够正确匹配诊断结果并触发动作。

测试流程：
1. 查询最近的异常采样
2. 检查是否有关联的自动化任务
3. 验证任务是否匹配到策略
4. 检查任务状态和执行结果

使用方法：
    python3 test_policy_matching.py
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import SessionLocal
from models.automation import (
    AutomationPolicy, AutomationTask, LogSample, LogAnalysisResult
)
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_policy_matching():
    """测试策略匹配"""
    db = SessionLocal()

    try:
        logger.info("=== 开始测试策略匹配 ===\n")

        # 1. 查询所有策略
        policies = db.query(AutomationPolicy).filter(
            AutomationPolicy.enabled == True
        ).all()

        logger.info(f"✓ 已启用的策略数量: {len(policies)}")
        for policy in policies:
            logger.info(f"  - {policy.policy_code}: {policy.trigger_condition.get('diagnosis_type')}")
        logger.info("")

        # 2. 查询最近的异常采样
        samples = db.query(LogSample).filter(
            LogSample.is_abnormal == True
        ).order_by(LogSample.sampled_at.desc()).limit(5).all()

        logger.info(f"✓ 最近的异常采样数量: {len(samples)}")
        logger.info("")

        # 3. 检查每个采样是否有关联的任务
        for sample in samples:
            logger.info(f"--- 采样ID: {sample.id} ---")
            logger.info(f"  设备IP: {sample.raw_data.get('device_ip') if sample.raw_data else 'N/A'}")
            logger.info(f"  异常类型: {sample.abnormal_type}")
            logger.info(f"  采样时间: {sample.sampled_at}")

            # 查询关联的分析结果
            analysis_result = db.query(LogAnalysisResult).filter(
                LogAnalysisResult.related_sample_id == sample.id
            ).first()

            if analysis_result:
                logger.info(f"  ✓ 有关联的研判结果 (ID: {analysis_result.id})")
                logger.info(f"    诊断类型: {analysis_result.analysis_type}")
                logger.info(f"    置信度: {analysis_result.confidence}")
                logger.info(f"    摘要: {analysis_result.summary[:100] if analysis_result.summary else 'N/A'}...")
            else:
                logger.info(f"  ✗ 没有关联的研判结果")

            # 查询关联的自动化任务
            task = db.query(AutomationTask).filter(
                AutomationTask.trigger_event.op('->>')('source_id') == str(sample.id)
            ).first()

            if task:
                logger.info(f"  ✓ 有关联的自动化任务 (ID: {task.id})")
                logger.info(f"    任务代码: {task.task_code}")
                logger.info(f"    策略ID: {task.policy_id}")
                logger.info(f"    状态: {task.status}")
                logger.info(f"    触发者: {task.triggered_by}")

                # 检查是否匹配到策略
                if task.policy_id:
                    policy = db.query(AutomationPolicy).filter(
                        AutomationPolicy.id == task.policy_id
                    ).first()
                    if policy:
                        logger.info(f"    ✓ 匹配到策略: {policy.policy_code}")
                        logger.info(f"      策略名称: {policy.policy_name}")
                        logger.info(f"      风险等级: {policy.risk_level}")
                        logger.info(f"      需确认: {policy.require_confirm}")
                else:
                    logger.info(f"  ⚠ 未匹配到策略（policy_id为None）")

                # 检查决策结果
                if task.decision_result:
                    decision = task.decision_result
                    diagnosis = decision.get("diagnosis", {})
                    logger.info(f"    决策结果:")
                    logger.info(f"      诊断类型: {diagnosis.get('diagnosis_type')}")
                    logger.info(f"      风险等级: {diagnosis.get('risk_level')}")
                    logger.info(f"      摘要: {diagnosis.get('summary', 'N/A')[:100]}...")

                # 检查执行结果
                if task.execution_result:
                    logger.info(f"    执行结果:")
                    logger.info(f"      状态: {task.execution_result.get('status')}")
                    logger.info(f"      消息: {task.execution_result.get('message', 'N/A')[:100]}...")
            else:
                logger.info(f"  ✗ 没有关联的自动化任务")

            logger.info("")

        # 4. 统计信息
        logger.info("=== 统计信息 ===")

        total_samples = db.query(LogSample).filter(
            LogSample.is_abnormal == True
        ).count()

        samples_with_analysis = db.query(LogSample.id).filter(
            LogSample.is_abnormal == True,
            LogSample.id.in_(
                db.query(LogAnalysisResult.related_sample_id).filter(
                    LogAnalysisResult.related_sample_id.isnot(None)
                )
            )
        ).count()

        samples_with_task = db.query(AutomationTask.id).filter(
            AutomationTask.triggered_by == "log_sample"
        ).count()

        tasks_with_policy = db.query(AutomationTask).filter(
            AutomationTask.policy_id.isnot(None)
        ).count()

        logger.info(f"  总异常采样数: {total_samples}")
        logger.info(f"  有研判结果的采样数: {samples_with_analysis} ({samples_with_analysis/total_samples*100:.1f}%)")
        logger.info(f"  有自动化任务数: {samples_with_task}")
        logger.info(f"  匹配到策略的任务数: {tasks_with_policy} ({tasks_with_policy/samples_with_task*100 if samples_with_task > 0 else 0:.1f}%)")

        # 5. 检查策略匹配率
        logger.info("\n=== 策略匹配分析 ===")

        for policy in policies:
            diagnosis_type = policy.trigger_condition.get('diagnosis_type')
            if diagnosis_type:
                # 查询该诊断类型的任务数
                task_count = db.query(AutomationTask).filter(
                    AutomationTask.policy_id == policy.id
                ).count()

                logger.info(f"  {policy.policy_code}:")
                logger.info(f"    诊断类型: {diagnosis_type}")
                logger.info(f"    匹配任务数: {task_count}")

        logger.info("\n=== 测试完成 ===")

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    test_policy_matching()
