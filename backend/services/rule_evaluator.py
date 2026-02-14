"""
规则评估器 - 针对网络设备的基础规则判断
"""
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from services.rule_engine import (
    Rule, RuleCondition, RuleAction, RuleEngine,
    ThresholdCondition, CompositeCondition, DiagnosisAction
)
from database import SessionLocal

logger = logging.getLogger(__name__)


class NetworkRuleEvaluator:
    """网络设备规则评估器"""

    def __init__(self):
        """初始化规则评估器"""
        self.rule_engine = RuleEngine()
        self._init_default_rules()

    def _init_default_rules(self):
        """初始化默认规则"""
        # 规则1: CRC错误过高
        # 注意：规则阈值应该与采样阈值协调
        # 采样阈值：CRC=5（记录为异常）
        # 规则阈值：CRC=5（触发诊断）
        rule_crc_high = Rule(
            rule_id="RULE_CRC_HIGH",
            name="CRC错误过高诊断规则",
            condition=ThresholdCondition(
                field="crc_error_count",
                operator=">=",
                value=5
            ),
            action=DiagnosisAction(
                diagnosis_type="LINK_QUALITY_DEGRADE",
                severity="medium",
                recommendations=[
                    "检查光模块是否老化或接触不良",
                    "更换光模块或光纤跳线验证",
                    "检查对端设备状态"
                ]
            )
        )
        self.rule_engine.add_rule(rule_crc_high)

        # 规则2: 接口频繁flap
        # 采样阈值：Flap=30（记录为异常）
        # 规则阈值：Flap=30（触发诊断）
        rule_flap_high = Rule(
            rule_id="RULE_FLAP_HIGH",
            name="接口频繁flap诊断规则",
            condition=ThresholdCondition(
                field="flap_count",
                operator=">=",
                value=30
            ),
            action=DiagnosisAction(
                diagnosis_type="INTERFACE_FLAP",
                severity="medium",
                recommendations=[
                    "检查接口配置是否有误",
                    "检查链路稳定性",
                    "检查对端设备状态",
                    "排查物理连接问题"
                ]
            )
        )
        self.rule_engine.add_rule(rule_flap_high)

        # 规则2b: 接口状态变化（up/down）在周期内高频出现
        rule_interface_state_burst = Rule(
            rule_id="RULE_INTERFACE_STATE_BURST",
            name="接口状态变化高频诊断规则",
            condition=ThresholdCondition(
                field="interface_state_change_count",
                operator=">=",
                value=30
            ),
            action=DiagnosisAction(
                diagnosis_type="INTERFACE_FLAP",
                severity="medium",
                recommendations=[
                    "检查接口物理层及收发光模块",
                    "检查接口协商与双工配置",
                    "核查最近配置变更与维护窗口",
                    "必要时抓取端口事件时间线"
                ]
            )
        )
        self.rule_engine.add_rule(rule_interface_state_burst)

        # 规则3: 邻居变化频繁
        # 采样阈值：邻居=15（记录为异常）
        # 规则阈值：邻居=15（触发诊断）
        rule_neighbor_unstable = Rule(
            rule_id="RULE_NEIGHBOR_UNSTABLE",
            name="邻居变化频繁诊断规则",
            condition=ThresholdCondition(
                field="neighbor_change_count",
                operator=">=",
                value=15
            ),
            action=DiagnosisAction(
                diagnosis_type="NEIGHBOR_UNSTABLE",
                severity="medium",
                recommendations=[
                    "检查路由协议配置",
                    "检查网络拓扑变化",
                    "检查对端设备状态",
                    "排查路由震荡问题"
                ]
            )
        )
        self.rule_engine.add_rule(rule_neighbor_unstable)

        # 规则4: 综合异常（CRC高 + Flap高）
        rule_combined = Rule(
            rule_id="RULE_COMBINED_CRC_FLAP",
            name="综合异常诊断规则（CRC+Flap）",
            condition=CompositeCondition(
                conditions=[
                    ThresholdCondition(
                        field="crc_error_count",
                        operator=">=",
                        value=5
                    ),
                    ThresholdCondition(
                        field="flap_count",
                        operator=">=",
                        value=30
                    )
                ],
                logic="AND"
            ),
            action=DiagnosisAction(
                diagnosis_type="COMBINED_LINK_ISSUE",
                severity="high",
                recommendations=[
                    "立即检查物理链路（光模块、光纤）",
                    "检查两端设备配置",
                    "考虑更换硬件设备",
                    "联系网络工程师现场排查"
                ]
            )
        )
        self.rule_engine.add_rule(rule_combined)

        # 规则5: 错误计数过高
        # 采样阈值：错误=10（记录为异常）
        # 规则阈值：错误=15（触发诊断）
        rule_error_high = Rule(
            rule_id="RULE_ERROR_HIGH",
            name="错误计数过高诊断规则",
            condition=ThresholdCondition(
                field="error_count",
                operator=">=",
                value=15
            ),
            action=DiagnosisAction(
                diagnosis_type="HIGH_ERROR_RATE",
                severity="medium",
                recommendations=[
                    "检查接口配置",
                    "检查链路质量",
                    "检查流量负载",
                    "排查网络拥塞问题"
                ]
            )
        )
        self.rule_engine.add_rule(rule_error_high)

        # 规则6: 严重日志实时触发
        rule_critical_log = Rule(
            rule_id="RULE_CRITICAL_LOG_IMMEDIATE",
            name="严重日志实时触发规则",
            condition=ThresholdCondition(
                field="critical_event_count",
                operator=">=",
                value=1
            ),
            action=DiagnosisAction(
                diagnosis_type="HARDWARE_ISSUE",
                severity="high",
                recommendations=[
                    "立即核查设备硬件健康（电源/风扇/温度/光模块）",
                    "核查同链路对端是否存在同步告警",
                    "触发SSH实时采集并优先人工复核"
                ]
            )
        )
        self.rule_engine.add_rule(rule_critical_log)

        logger.info(f"Initialized {len(self.rule_engine.rules)} default rules")

    def evaluate_log_sample(
        self,
        site_id: int,
        netbox_device_id: Optional[int],
        device_stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        评估日志采样

        Args:
            site_id: 基地ID
            netbox_device_id: 设备ID
            device_stats: 设备统计数据

        Returns:
            匹配的规则结果列表
        """
        results = []

        # 使用规则引擎评估
        matched_rules = self.rule_engine.evaluate(device_stats)

        for rule_result in matched_rules:
            results.append({
                "rule_id": rule_result["rule_id"],
                "rule_name": rule_result["rule_name"],
                "result": rule_result["result"]
            })

        return results


# 全局规则评估器实例
rule_evaluator = NetworkRuleEvaluator()
