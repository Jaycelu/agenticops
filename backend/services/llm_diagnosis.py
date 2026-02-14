"""
LLM诊断服务 - 使用LLM进行综合研判
"""
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from models.llm_client import LLMClient
from services.schemas import (
    DiagnosisResult, SeverityLevel, DiagnosisType, Evidence
)
from config.settings import settings

logger = logging.getLogger(__name__)


class LLMDiagnosisService:
    """LLM诊断服务"""

    def __init__(self):
        """初始化LLM诊断服务"""
        self.llm_client = LLMClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_url,
            model=settings.llm_model_name
        )

    async def diagnose_log_sample(
        self,
        site_id: int,
        device_ip: str,
        device_stats: Dict[str, Any],
        device_info: Optional[Dict[str, Any]] = None
    ) -> DiagnosisResult:
        """
        使用LLM诊断日志采样

        Args:
            site_id: 基地ID
            device_ip: 设备IP
            device_stats: 设备统计数据
            device_info: 设备信息（从NetBox获取）

        Returns:
            诊断结果
        """
        # 构建LLM提示词
        prompt = self._build_diagnosis_prompt(
            site_id, device_ip, device_stats, device_info
        )

        try:
            # 调用LLM
            response = await self.llm_client.chat_completion_with_json(
                messages=prompt,
                temperature=0.3,
                timeout=30.0
            )

            # 解析LLM响应
            diagnosis = self._parse_diagnosis_response(response, device_stats)

            logger.info(f"LLM diagnosis completed for {device_ip}: {diagnosis.diagnosis_type}")
            return diagnosis

        except Exception as e:
            logger.error(f"LLM diagnosis failed for {device_ip}: {e}", exc_info=True)
            # 返回默认诊断结果
            return self._create_fallback_diagnosis(device_stats, str(e))

    def _build_diagnosis_prompt(
        self,
        site_id: int,
        device_ip: str,
        device_stats: Dict[str, Any],
        device_info: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        构建LLM诊断提示词

        Args:
            site_id: 基地ID
            device_ip: 设备IP
            device_stats: 设备统计数据
            device_info: 设备信息

        Returns:
            消息列表
        """
        system_prompt = """你是一位资深的网络运维专家，擅长分析网络设备日志和指标，诊断网络问题。

请根据提供的设备指标和日志信息，进行综合研判，输出JSON格式的诊断结果。

诊断类型包括：
- LINK_QUALITY_DEGRADE: 链路质量下降（CRC错误、丢包等）
- INTERFACE_FLAP: 接口频繁震荡
- NEIGHBOR_UNSTABLE: 邻居关系不稳定
- COMBINED_LINK_ISSUE: 综合链路问题（多种异常同时存在）
- HIGH_ERROR_RATE: 高错误率
- CONFIGURATION_ISSUE: 配置问题
- HARDWARE_ISSUE: 硬件问题
- UNKNOWN: 未知问题

严重程度包括：
- low: 低
- medium: 中
- high: 高
- critical: 严重

请按照以下JSON格式输出：
{
    "diagnosis_type": "诊断类型",
    "severity": "严重程度",
    "confidence": 0.0-1.0之间的置信度,
    "summary": "诊断摘要（1-2句话）",
    "evidence": [
        {
            "type": "证据类型",
            "value": "证据值",
            "description": "证据描述"
        }
    ],
    "recommendations": ["建议1", "建议2", "建议3"],
    "risk_level": "风险等级",
    "require_human_confirm": true/false
}

注意：
1. 置信度应该基于证据的充分性
2. 证据应该从提供的指标中提取
3. 建议应该具体、可执行
4. 如果问题复杂或风险高，require_human_confirm应该为true
"""

        # 构建用户提示词
        user_prompt = f"""请诊断以下网络设备的问题：

【设备信息】
- 设备IP: {device_ip}
- 基地ID: {site_id}
"""

        if device_info:
            user_prompt += f"""
- 设备名称: {device_info.get('name', '未知')}
- 设备类型: {device_info.get('device_type', '未知')}
- 设备角色: {device_info.get('role', '未知')}
- 主IP: {device_info.get('primary_ip', '未知')}
"""

        user_prompt += f"""
【设备指标】
- CRC错误计数: {device_stats.get('crc_error_count', 0)}
- 接口flap次数: {device_stats.get('flap_count', 0)}
- 邻居变化次数: {device_stats.get('neighbor_change_count', 0)}
- 错误计数: {device_stats.get('error_count', 0)}
"""

        # 添加日志消息（如果有）
        log_messages = device_stats.get('log_messages', [])
        if log_messages:
            user_prompt += f"""
【日志消息】（最近{min(5, len(log_messages))}条）
"""
            for msg in log_messages[:5]:
                user_prompt += f"- {msg[:200]}...\n"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _parse_diagnosis_response(
        self,
        response: Dict[str, Any],
        device_stats: Dict[str, Any]
    ) -> DiagnosisResult:
        """
        解析LLM诊断响应

        Args:
            response: LLM响应
            device_stats: 设备统计数据

        Returns:
            诊断结果
        """
        # 解析证据
        evidence = []
        for ev in response.get("evidence", []):
            evidence.append(Evidence(
                type=ev.get("type", "unknown"),
                value=ev.get("value"),
                description=ev.get("description", "")
            ))

        # 如果没有证据，从device_stats中提取
        if not evidence:
            evidence = self._extract_evidence_from_stats(device_stats)

        # 创建诊断结果
        return DiagnosisResult(
            diagnosis_type=DiagnosisType(response.get("diagnosis_type", "UNKNOWN")),
            severity=SeverityLevel(response.get("severity", "medium")),
            confidence=float(response.get("confidence", 0.7)),
            summary=response.get("summary", "LLM诊断完成"),
            evidence=evidence,
            recommendations=response.get("recommendations", [
                "请人工确认设备状态"
            ]),
            risk_level=SeverityLevel(response.get("risk_level", "medium")),
            require_human_confirm=bool(response.get("require_human_confirm", False))
        )

    def _extract_evidence_from_stats(self, device_stats: Dict[str, Any]) -> List[Evidence]:
        """
        从设备统计中提取证据

        Args:
            device_stats: 设备统计数据

        Returns:
            证据列表
        """
        evidence = []

        if device_stats.get("crc_error_count", 0) > 0:
            evidence.append(Evidence(
                type="crc_error_count",
                value=device_stats["crc_error_count"],
                description=f"CRC错误计数为{device_stats['crc_error_count']}"
            ))

        if device_stats.get("flap_count", 0) > 0:
            evidence.append(Evidence(
                type="flap_count",
                value=device_stats["flap_count"],
                description=f"接口flap次数为{device_stats['flap_count']}"
            ))

        if device_stats.get("neighbor_change_count", 0) > 0:
            evidence.append(Evidence(
                type="neighbor_change_count",
                value=device_stats["neighbor_change_count"],
                description=f"邻居变化次数为{device_stats['neighbor_change_count']}"
            ))

        if device_stats.get("error_count", 0) > 0:
            evidence.append(Evidence(
                type="error_count",
                value=device_stats["error_count"],
                description=f"错误计数为{device_stats['error_count']}"
            ))

        return evidence

    def _create_fallback_diagnosis(
        self,
        device_stats: Dict[str, Any],
        error_message: str
    ) -> DiagnosisResult:
        """
        创建回退诊断结果（当LLM调用失败时）

        Args:
            device_stats: 设备统计数据
            error_message: 错误消息

        Returns:
            诊断结果
        """
        evidence = self._extract_evidence_from_stats(device_stats)

        return DiagnosisResult(
            diagnosis_type=DiagnosisType.UNKNOWN,
            severity=SeverityLevel.MEDIUM,
            confidence=0.5,
            summary=f"LLM诊断失败，使用规则引擎结果。错误: {error_message}",
            evidence=evidence,
            recommendations=[
                "请人工确认设备状态",
                "检查系统日志以获取更多信息"
            ],
            risk_level=SeverityLevel.MEDIUM,
            require_human_confirm=True
        )


# 全局LLM诊断服务实例
llm_diagnosis_service = LLMDiagnosisService()