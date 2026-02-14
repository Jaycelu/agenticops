"""
基地配置文件
定义各基地与ELK查询条件的映射
直接复用ELKMCP中的base_configs
"""
from typing import Dict, List, Optional
from mcp.elk_mcp import ELKMCP


# 获取ELKMCP实例以访问base_configs
elk_mcp = ELKMCP()

# 默认采样配置（适用于所有基地）
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
    根据基地代码获取基地配置
    直接从ELKMCP的base_configs获取，并附加采样和研判配置

    Args:
        site_code: 基地代码

    Returns:
        基地配置字典，如果不存在则返回None
    """
    # 转换为小写以匹配ELKMCP的键
    site_code_lower = site_code.lower()

    if site_code_lower not in elk_mcp.base_configs:
        return None

    base_config = elk_mcp.base_configs[site_code_lower]

    # 构建完整的基地配置
    config = {
        "site_code": site_code.upper(),
        "site_name": base_config["name"],
        "description": f"{base_config['name']}网络设备",
        "elk_query": {
            "filter": base_config["filter"],
            "time_range": base_config["time_range"]
        },
        "sampling": DEFAULT_SAMPLING_CONFIG,
        "diagnosis_policy": DEFAULT_DIAGNOSIS_POLICY
    }

    return config


def get_all_sites() -> List[str]:
    """
    获取所有已配置的基地代码列表
    直接从ELKMCP的base_configs获取

    Returns:
        基地代码列表（大写）
    """
    return [code.upper() for code in elk_mcp.base_configs.keys()]


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
