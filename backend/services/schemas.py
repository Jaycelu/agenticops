"""
自动化决策结果数据模型定义
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class SeverityLevel(str, Enum):
    """严重程度枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    WARNING = "warning"


class DiagnosisType(str, Enum):
    """诊断类型枚举"""
    LINK_QUALITY_DEGRADE = "LINK_QUALITY_DEGRADE"
    INTERFACE_FLAP = "INTERFACE_FLAP"
    NEIGHBOR_UNSTABLE = "NEIGHBOR_UNSTABLE"
    COMBINED_LINK_ISSUE = "COMBINED_LINK_ISSUE"
    HIGH_ERROR_RATE = "HIGH_ERROR_RATE"
    CONFIGURATION_ISSUE = "CONFIGURATION_ISSUE"
    HARDWARE_ISSUE = "HARDWARE_ISSUE"
    UNKNOWN = "UNKNOWN"


class Evidence(BaseModel):
    """证据"""
    type: str = Field(..., description="证据类型")
    value: Any = Field(..., description="证据值")
    description: str = Field(..., description="证据描述")


class DiagnosisResult(BaseModel):
    """诊断结果"""
    diagnosis_type: DiagnosisType = Field(..., description="诊断类型")
    severity: SeverityLevel = Field(..., description="严重程度")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="置信度")
    summary: str = Field(..., description="诊断摘要")
    evidence: List[Evidence] = Field(default_factory=list, description="证据列表")
    recommendations: List[str] = Field(default_factory=list, description="建议列表")
    risk_level: SeverityLevel = Field(default=SeverityLevel.MEDIUM, description="风险等级")
    require_human_confirm: bool = Field(default=False, description="是否需要人工确认")

    class Config:
        json_schema_extra = {
            "example": {
                "diagnosis_type": "LINK_QUALITY_DEGRADE",
                "severity": "warning",
                "confidence": 0.85,
                "summary": "接口CRC错误持续增长，可能是光模块老化或物理链路问题",
                "evidence": [
                    {
                        "type": "crc_error_count",
                        "value": 15,
                        "description": "CRC错误计数为15，超过阈值10"
                    },
                    {
                        "type": "flap_count",
                        "value": 0,
                        "description": "接口无flap现象"
                    }
                ],
                "recommendations": [
                    "检查光模块是否老化或接触不良",
                    "更换光模块或光纤跳线验证",
                    "检查对端设备状态"
                ],
                "risk_level": "medium",
                "require_human_confirm": False
            }
        }


class DecisionResult(BaseModel):
    """决策结果"""
    rule_id: Optional[str] = Field(None, description="匹配的规则ID")
    rule_name: Optional[str] = Field(None, description="匹配的规则名称")
    diagnosis: DiagnosisResult = Field(..., description="诊断结果")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": "RULE_CRC_HIGH",
                "rule_name": "CRC错误过高诊断规则",
                "diagnosis": {
                    "diagnosis_type": "LINK_QUALITY_DEGRADE",
                    "severity": "warning",
                    "confidence": 0.85,
                    "summary": "接口CRC错误持续增长，可能是光模块老化或物理链路问题",
                    "evidence": [
                        {
                            "type": "crc_error_count",
                            "value": 15,
                            "description": "CRC错误计数为15，超过阈值10"
                        }
                    ],
                    "recommendations": [
                        "检查光模块是否老化或接触不良",
                        "更换光模块或光纤跳线验证"
                    ],
                    "risk_level": "medium",
                    "require_human_confirm": False
                },
                "context": {
                    "site_id": 1,
                    "device_ip": "10.128.242.37",
                    "crc_error_count": 15,
                    "flap_count": 0,
                    "neighbor_change_count": 0,
                    "error_count": 4
                },
                "created_at": "2026-01-14T09:00:00"
            }
        }


class ExecutionResult(BaseModel):
    """执行结果"""
    status: str = Field(..., description="执行状态：success, failed, aborted")
    message: str = Field(..., description="执行消息")
    details: Dict[str, Any] = Field(default_factory=dict, description="执行详情")
    executed_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="执行时间")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "诊断任务执行成功",
                "details": {
                    "actions_taken": ["规则匹配", "生成诊断结论"],
                    "duration_ms": 150
                },
                "executed_at": "2026-01-14T09:00:01"
            }
        }


class TaskTriggerEvent(BaseModel):
    """任务触发事件"""
    event_type: str = Field(..., description="事件类型：log_sample, raw_anomaly, manual")
    source_id: Optional[int] = Field(None, description="来源ID（log_sample_id或raw_anomaly_id）")
    source_type: Optional[str] = Field(None, description="来源类型")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "log_sample",
                "source_id": 123,
                "source_type": "LogSample",
                "data": {
                    "site_id": 1,
                    "device_ip": "10.128.242.37",
                    "crc_error_count": 15,
                    "flap_count": 0
                }
            }
        }