"""
基地配置文件
定义站点与日志范围的映射

事件中心侧路由阈值（24h 集群计数、跨源关联窗口等）与 enrich 共用常量见：
config/pipeline_thresholds.py
"""
from typing import Dict, List, Optional
from database import SessionLocal
from services.log_scope_service import log_scope_service


# 默认采样配置（适用于所有基地）
# 说明：abnormal_tracker 与 log_collection_policy 控制「何时产生强信号 / 建 Case」；
# 与 EventDecisionService.enrich 的 CLUSTER_COUNT_* / CROSS_SOURCE_* 配合形成端到端降噪，运维时请对照 pipeline_thresholds 一并调整。
DEFAULT_SAMPLING_CONFIG = {
    # 采样时间窗口（分钟）
    "time_window_minutes": 15,

    # 采样间隔（分钟）
    "sampling_interval_minutes": 15,

    # 异常阈值配置（根据实际数据调整）
    # 基于24小时数据分析（460条采样）：
    # - CRC错误: 无数据（目前设备没有CRC错误）
    # - Flap次数: 平均值38.16, 中位数49, 95分位63
    # - 邻居变化: 平均值42.06, 中位数11, 95分位131
    # - 错误包数: 平均值5.32, 中位数2, 95分位14
    "thresholds": {
        # CRC错误阈值（15分钟内超过此值视为异常）
        # 设置为5，基于实际数据调整
        "crc_error_threshold": 5,

        # 接口flap阈值（15分钟内flap次数）
        # 基于中位数49，设置为60可以捕获严重的flap问题
        "flap_threshold": 60,

        # 邻居变化阈值（15分钟内邻居变化次数）
        # 基于中位数11，设置为30可以捕获严重的邻居不稳定问题
        "neighbor_change_threshold": 30,

        # 错误包数阈值（15分钟内错误包数）
        # 基于中位数2，设置为10可以捕获明显的问题
        "error_count_threshold": 10,

        # 其他错误日志阈值（15分钟内其他错误日志数量）
        # 保持20，因为这是额外的错误类型
        "other_error_threshold": 20
    },

    # 异常跟踪器配置
    "abnormal_tracker": {
        # 累积阈值：同一台设备的同一种异常需要连续多少次采样才触发研判
        # 采样间隔15分钟，3次异常 = 45分钟的持续异常
        "accumulation_threshold": 3,

        # 去重时间窗口（分钟）：同一台设备的同一种异常在此时间窗口内只触发一次
        "dedup_window_minutes": 120,

        # 冷却时间（分钟）：同一台设备的同一种异常触发后需要等待多久才能再次触发
        "cooldown_minutes": 120
    },

    # 日志采集与触发策略（分层）
    "log_collection_policy": {
        # 严重日志：实时进入异常判定和自动化
        "urgent_levels": ["Critical", "Alert", "Emergencies"],
        "urgent_keywords": [
            "kernel panic", "power fail", "fan fail", "temperature critical",
            "optical module fault", "los", "cpu hog", "memory exhausted",
            "bgp down", "ospf down", "isis down", "authentication failed"
        ],
        "message_dedup_seconds": 120,
        "immediate_trigger": {
            "critical_event_count": 1,
            "hardware_alarm_count": 1,
            "auth_failure_count": 10
        },
        # 普通日志：按周期累计触发（接口up/down示例已内置）
        "periodic_trigger": {
            "interface_state_change_count": {
                "window_minutes": 1440,
                "threshold": 30,
                "abnormal_type": "INTERFACE_FLAP",
                "risk_level": "medium"
            },
            "neighbor_change_count": {
                "window_minutes": 1440,
                "threshold": 40,
                "abnormal_type": "NEIGHBOR_UNSTABLE",
                "risk_level": "medium"
            },
            "routing_instability_count": {
                "window_minutes": 720,
                "threshold": 20,
                "abnormal_type": "NEIGHBOR_UNSTABLE",
                "risk_level": "high"
            },
            "error_count": {
                "window_minutes": 60,
                "threshold": 80,
                "abnormal_type": "HIGH_ERROR_RATE",
                "risk_level": "medium"
            }
        }
    }
}

# 默认研判策略配置（适用于所有基地）
DEFAULT_DIAGNOSIS_POLICY = {
    # 启用的研判类型
    "enabled_diagnosis_types": [
        "LINK_QUALITY_DEGRADE",  # 链路质量下降
        "INTERFACE_FLAP",        # 接口震荡
        "NEIGHBOR_UNSTABLE",     # 邻居不稳定
        "DEVICE_HEALTH_CHECK"    # 设备健康检查
    ],

    # 风险等级定义
    "risk_levels": {
        "low": {
            "description": "低风险，建议关注",
            "auto_execute": False
        },
        "medium": {
            "description": "中等风险，需要人工确认",
            "auto_execute": False,
            "require_confirm": True
        },
        "high": {
            "description": "高风险，必须人工确认",
            "auto_execute": False,
            "require_confirm": True
        }
    },
    # 自动化任务触发策略
    "task_trigger_policy": {
        # 仅当风险等级 >= min_severity 且置信度 >= min_confidence 时才创建自动化任务
        "min_severity": "medium",
        "min_confidence": 0.6,
        # 可自动执行的建议动作类型（其余转人工确认）
        "auto_action_types": ["config_optimization"],
        # 这些动作类型强制进入人工确认流
        "manual_action_types": ["replace_hardware", "manual_investigation"],
    }
}

# 反馈学习策略（默认）
DEFAULT_FEEDBACK_LEARNING_POLICY = {
    "window_days": 30,
    "min_samples": 5,
    "incorrect_rate_threshold": 0.4,
    "correct_rate_threshold": 0.8,
    "confidence_decrease_factor": 0.7,
    "confidence_increase_value": 0.1
}

# 可选：按基地/诊断类型覆盖反馈学习策略
# 结构示例：
# {
#   "DEYANG": {
#     "default": {"window_days": 30, "min_samples": 8},
#     "by_diagnosis_type": {
#       "LINK_QUALITY_DEGRADE": {"min_samples": 10}
#     }
#   }
# }
FEEDBACK_LEARNING_OVERRIDES: Dict[str, Dict] = {}


def get_site_config(site_code: str) -> Optional[dict]:
    """
    根据站点代码获取绑定的日志范围配置，并附加采样和研判配置

    Args:
        site_code: 基地代码

    Returns:
        基地配置字典，如果不存在则返回None
    """
    db = SessionLocal()
    try:
        scope = log_scope_service.resolve_scope(db=db, site_code=site_code)
    finally:
        db.close()
    if not scope:
        return None

    # 构建完整的基地配置
    config = {
        "site_code": site_code.upper(),
        "site_name": scope["display_name"],
        "description": f"{scope['display_name']}网络设备",
        "elk_query": {
            "scope_key": scope["scope_key"],
            "filter": scope["query_filter"],
            "time_range": scope["default_time_range"],
        },
        "sampling": DEFAULT_SAMPLING_CONFIG,
        "diagnosis_policy": DEFAULT_DIAGNOSIS_POLICY
    }

    return config


def get_all_sites() -> List[str]:
    """
    获取所有已绑定日志范围的站点代码列表

    Returns:
        基地代码列表（大写）
    """
    return log_scope_service.list_bound_site_codes()


def get_elk_query_for_site(site_code: str) -> Optional[dict]:
    """
    获取指定基地的ELK查询配置

    Args:
        site_code: 基地代码

    Returns:
        ELK查询配置字典
    """
    config = get_site_config(site_code)
    if config:
        return config.get("elk_query")
    return None


def get_sampling_thresholds(site_code: str) -> Optional[dict]:
    """
    获取指定基地的采样阈值配置

    Args:
        site_code: 基地代码

    Returns:
        采样阈值配置字典
    """
    config = get_site_config(site_code)
    if config:
        return config.get("sampling", {}).get("thresholds")
    return None


def get_log_collection_policy(site_code: str) -> Optional[dict]:
    """
    获取指定基地的日志采集策略
    """
    config = get_site_config(site_code)
    if config:
        return config.get("sampling", {}).get("log_collection_policy", {})
    return None


def get_feedback_learning_policy(site_code: Optional[str], diagnosis_type: Optional[str] = None) -> dict:
    """
    获取反馈学习策略，支持按基地/诊断类型覆盖。

    Args:
        site_code: 基地代码（如 DEYANG）
        diagnosis_type: 诊断类型（可选）

    Returns:
        策略字典
    """
    policy = dict(DEFAULT_FEEDBACK_LEARNING_POLICY)
    if not site_code:
        return policy

    override = FEEDBACK_LEARNING_OVERRIDES.get(site_code.upper(), {})
    if not override:
        return policy

    policy.update(override.get("default", {}))
    if diagnosis_type:
        by_type = override.get("by_diagnosis_type", {})
        policy.update(by_type.get(diagnosis_type, {}))
    return policy


def get_task_trigger_policy(site_code: Optional[str]) -> dict:
    """
    获取自动化任务触发策略。
    """
    default_policy = DEFAULT_DIAGNOSIS_POLICY.get("task_trigger_policy", {})
    if not site_code:
        return dict(default_policy)
    config = get_site_config(site_code)
    if not config:
        return dict(default_policy)
    diagnosis_policy = config.get("diagnosis_policy", {})
    site_policy = diagnosis_policy.get("task_trigger_policy", {})
    merged = dict(default_policy)
    merged.update(site_policy)
    return merged
