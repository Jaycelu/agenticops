"""
规则引擎 - 用于自动化决策的规则判断系统
"""
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

from database import SessionLocal

logger = logging.getLogger(__name__)


class RuleCondition(ABC):
    """规则条件基类"""

    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        评估条件是否满足

        Args:
            context: 上下文数据（设备状态、日志采样等）

        Returns:
            是否满足条件
        """
        pass

    @abstractmethod
    def description(self) -> str:
        """
        获取条件描述

        Returns:
            条件描述文本
        """
        pass


class ThresholdCondition(RuleCondition):
    """阈值条件"""

    def __init__(self, field: str, operator: str, value: float):
        """
        初始化阈值条件

        Args:
            field: 字段名
            operator: 操作符（>, >=, <, <=, ==, !=）
            value: 阈值
        """
        self.field = field
        self.operator = operator
        self.value = value

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        评估阈值条件

        Args:
            context: 上下文数据

        Returns:
            是否满足条件
        """
        field_value = context.get(self.field)
        if field_value is None:
            return False

        try:
            field_value = float(field_value)
            if self.operator == ">":
                return field_value > self.value
            elif self.operator == ">=":
                return field_value >= self.value
            elif self.operator == "<":
                return field_value < self.value
            elif self.operator == "<=":
                return field_value <= self.value
            elif self.operator == "==":
                return field_value == self.value
            elif self.operator == "!=":
                return field_value != self.value
            else:
                logger.warning(f"Unknown operator: {self.operator}")
                return False
        except (ValueError, TypeError):
            logger.warning(f"Cannot convert {self.field} to float: {field_value}")
            return False

    def description(self) -> str:
        """
        获取条件描述

        Returns:
            条件描述文本
        """
        return f"{self.field} {self.operator} {self.value}"


class CompositeCondition(RuleCondition):
    """组合条件（AND/OR）"""

    def __init__(self, conditions: List[RuleCondition], logic: str = "AND"):
        """
        初始化组合条件

        Args:
            conditions: 子条件列表
            logic: 逻辑关系（AND/OR）
        """
        self.conditions = conditions
        self.logic = logic.upper()

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        评估组合条件

        Args:
            context: 上下文数据

        Returns:
            是否满足条件
        """
        if not self.conditions:
            return True

        if self.logic == "AND":
            return all(cond.evaluate(context) for cond in self.conditions)
        elif self.logic == "OR":
            return any(cond.evaluate(context) for cond in self.conditions)
        else:
            logger.warning(f"Unknown logic: {self.logic}")
            return False

    def description(self) -> str:
        """
        获取条件描述

        Returns:
            条件描述文本
        """
        op = " AND " if self.logic == "AND" else " OR "
        descriptions = [cond.description() for cond in self.conditions]
        return f"({op.join(descriptions)})"


class RuleAction(ABC):
    """规则动作基类"""

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行动作

        Args:
            context: 上下文数据

        Returns:
            执行结果
        """
        pass

    @abstractmethod
    def description(self) -> str:
        """
        获取动作描述

        Returns:
            动作描述文本
        """
        pass


class DiagnosisAction(RuleAction):
    """诊断动作 - 生成诊断结论"""

    def __init__(self, diagnosis_type: str, severity: str, recommendations: List[str], summary: Optional[str] = None):
        """
        初始化诊断动作

        Args:
            diagnosis_type: 诊断类型
            severity: 严重程度
            recommendations: 建议列表
            summary: 诊断摘要（可选）
        """
        self.diagnosis_type = diagnosis_type
        self.base_severity = severity
        self.recommendations = recommendations
        self.summary = summary or f"检测到{diagnosis_type}异常"

    def _calculate_dynamic_severity(self, context: Dict[str, Any], threshold: int) -> str:
        """
        根据异常值动态计算严重程度

        分级判定逻辑：
        - value < threshold * 1.5: low
        - threshold * 1.5 <= value < threshold * 2: medium
        - threshold * 2 <= value < threshold * 3: high
        - value >= threshold * 3: critical

        Args:
            context: 上下文数据
            threshold: 阈值

        Returns:
            动态计算的严重程度
        """
        # 根据诊断类型获取对应的字段和值
        field_mapping = {
            "LINK_QUALITY_DEGRADE": "crc_error_count",
            "INTERFACE_FLAP": "flap_count",
            "NEIGHBOR_UNSTABLE": "neighbor_change_count",
            "HIGH_ERROR_RATE": "error_count"
        }

        field_name = field_mapping.get(self.diagnosis_type)
        if not field_name:
            return self.base_severity

        value = context.get(field_name, 0)
        if value < threshold * 1.5:
            return "low"
        elif value < threshold * 2:
            return "medium"
        elif value < threshold * 3:
            return "high"
        else:
            return "critical"

    def execute(self, context: Dict[str, Any], threshold: int = 0) -> Dict[str, Any]:
        """
        执行诊断动作

        Args:
            context: 上下文数据
            threshold: 阈值（用于动态计算严重程度）

        Returns:
            诊断结果
        """
        # 如果提供了阈值，则动态计算严重程度
        if threshold > 0:
            severity = self._calculate_dynamic_severity(context, threshold)
        else:
            severity = self.base_severity

        return {
            "type": "diagnosis",
            "diagnosis_type": self.diagnosis_type,
            "severity": severity,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "context": context
        }

    def description(self) -> str:
        """
        获取动作描述

        Returns:
            动作描述文本
        """
        return f"Diagnosis: {self.diagnosis_type} (Severity: {self.base_severity})"


class Rule:
    """规则类 - 包含条件和动作"""

    def __init__(self, rule_id: str, name: str, condition: RuleCondition, action: RuleAction):
        """
        初始化规则

        Args:
            rule_id: 规则ID
            name: 规则名称
            condition: 规则条件
            action: 规则动作
        """
        self.rule_id = rule_id
        self.name = name
        self.condition = condition
        self.action = action

    def evaluate(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        评估规则

        Args:
            context: 上下文数据

        Returns:
            如果条件满足，返回执行结果；否则返回None
        """
        if self.condition.evaluate(context):
            logger.info(f"Rule {self.rule_id} ({self.name}) matched")

            # 获取阈值用于分级判定
            threshold = 0
            if isinstance(self.condition, ThresholdCondition):
                threshold = self.condition.value

            # 执行动作，传递阈值用于动态计算严重程度
            return self.action.execute(context, threshold)
        return None

    def description(self) -> str:
        """
        获取规则描述

        Returns:
            规则描述文本
        """
        return f"Rule {self.rule_id}: IF {self.condition.description()} THEN {self.action.description()}"


class RuleEngine:
    """规则引擎 - 管理和执行规则"""

    def __init__(self):
        """初始化规则引擎"""
        self.rules: Dict[str, Rule] = {}

    def add_rule(self, rule: Rule):
        """
        添加规则

        Args:
            rule: 规则对象
        """
        self.rules[rule.rule_id] = rule
        logger.info(f"Added rule: {rule.rule_id} ({rule.name})")

    def remove_rule(self, rule_id: str):
        """
        移除规则

        Args:
            rule_id: 规则ID
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed rule: {rule_id}")

    def evaluate(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        评估所有规则

        Args:
            context: 上下文数据

        Returns:
            匹配的规则执行结果列表
        """
        results = []
        for rule_id, rule in self.rules.items():
            result = rule.evaluate(context)
            if result:
                results.append({
                    "rule_id": rule_id,
                    "rule_name": rule.name,
                    "result": result
                })
        return results

    def evaluate_first(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        评估规则，返回第一个匹配的结果

        Args:
            context: 上下文数据

        Returns:
            第一个匹配的规则执行结果
        """
        for rule_id, rule in self.rules.items():
            result = rule.evaluate(context)
            if result:
                return {
                    "rule_id": rule_id,
                    "rule_name": rule.name,
                    "result": result
                }
        return None

    def list_rules(self) -> List[Dict[str, str]]:
        """
        列出所有规则

        Returns:
            规则列表
        """
        return [
            {
                "rule_id": rule_id,
                "rule_name": rule.name,
                "description": rule.description()
            }
            for rule_id, rule in self.rules.items()
        ]


# 全局规则引擎实例
rule_engine = RuleEngine()


class RuleParser:
    """规则解析器 - 从JSON解析规则"""

    @staticmethod
    def parse_condition(condition_json: Dict[str, Any]) -> RuleCondition:
        """
        解析条件JSON

        Args:
            condition_json: 条件JSON

        Returns:
            规则条件对象

        Raises:
            ValueError: 如果JSON格式无效
        """
        condition_type = condition_json.get("type")

        if condition_type == "threshold":
            # 阈值条件
            return ThresholdCondition(
                field=condition_json["field"],
                operator=condition_json["operator"],
                value=condition_json["value"]
            )
        elif condition_type == "composite":
            # 组合条件
            sub_conditions = [
                RuleParser.parse_condition(cond)
                for cond in condition_json["conditions"]
            ]
            return CompositeCondition(
                conditions=sub_conditions,
                logic=condition_json.get("logic", "AND")
            )
        else:
            raise ValueError(f"Unknown condition type: {condition_type}")

    @staticmethod
    def parse_action(action_json: Dict[str, Any]) -> RuleAction:
        """
        解析动作JSON

        Args:
            action_json: 动作JSON

        Returns:
            规则动作对象

        Raises:
            ValueError: 如果JSON格式无效
        """
        action_type = action_json.get("type")

        if action_type == "diagnosis":
            # 诊断动作
            return DiagnosisAction(
                diagnosis_type=action_json["diagnosis_type"],
                severity=action_json["severity"],
                recommendations=action_json["recommendations"]
            )
        else:
            raise ValueError(f"Unknown action type: {action_type}")

    @staticmethod
    def parse_rule(rule_json: Dict[str, Any]) -> Rule:
        """
        解析规则JSON

        Args:
            rule_json: 规则JSON

        Returns:
            规则对象

        Raises:
            ValueError: 如果JSON格式无效
        """
        condition = RuleParser.parse_condition(rule_json["condition"])
        action = RuleParser.parse_action(rule_json["action"])

        return Rule(
            rule_id=rule_json["rule_id"],
            name=rule_json["name"],
            condition=condition,
            action=action
        )


# 规则条件JSON规范示例
RULE_CONDITION_SCHEMA = {
    "threshold": {
        "type": "threshold",
        "field": "crc_error_count",  # 字段名
        "operator": ">=",              # 操作符: >, >=, <, <=, ==, !=
        "value": 10                    # 阈值
    },
    "composite": {
        "type": "composite",
        "logic": "AND",                # 逻辑关系: AND, OR
        "conditions": [                # 子条件列表
            {
                "type": "threshold",
                "field": "crc_error_count",
                "operator": ">=",
                "value": 10
            },
            {
                "type": "threshold",
                "field": "flap_count",
                "operator": ">",
                "value": 3
            }
        ]
    }
}

# 规则动作JSON规范示例
RULE_ACTION_SCHEMA = {
    "diagnosis": {
        "type": "diagnosis",
        "diagnosis_type": "LINK_QUALITY_DEGRADE",  # 诊断类型
        "severity": "warning",                      # 严重程度: low, medium, high, critical
        "recommendations": [                        # 建议列表
            "检查光模块是否老化或接触不良",
            "更换光模块或光纤跳线验证",
            "检查对端设备状态"
        ]
    }
}

# 完整规则JSON规范示例
RULE_SCHEMA = {
    "rule_id": "RULE_CRC_HIGH",
    "name": "CRC错误过高诊断规则",
    "condition": {
        "type": "threshold",
        "field": "crc_error_count",
        "operator": ">=",
        "value": 10
    },
    "action": {
        "type": "diagnosis",
        "diagnosis_type": "LINK_QUALITY_DEGRADE",
        "severity": "warning",
        "recommendations": [
            "检查光模块是否老化或接触不良",
            "更换光模块或光纤跳线验证"
        ]
    }
}