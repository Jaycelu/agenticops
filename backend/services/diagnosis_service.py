"""
研判服务
基于状态聚合结果进行设备问题研判
"""
import logging
from datetime import datetime
import json
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from services.state_aggregator import state_aggregator
from services.abnormal_upgrader import abnormal_upgrader
from models.llm_client import LLMClient
from config.settings import settings

logger = logging.getLogger(__name__)


# 证据模型
class EvidenceModel(BaseModel):
    """证据模型"""
    log_evidence: Dict[str, Any] = Field(default_factory=dict, description="日志证据")
    config_evidence: Dict[str, Any] = Field(default_factory=dict, description="配置证据")
    peer_evidence: Dict[str, Any] = Field(default_factory=dict, description="对端证据")
    trend_evidence: Dict[str, Any] = Field(default_factory=dict, description="趋势证据")


# 研判任务模板
class DiagnosisTask(BaseModel):
    """研判任务模板"""
    task_id: str
    site_id: int
    netbox_device_id: Optional[int] = None
    device_ip: Optional[str] = None
    device_name: Optional[str] = None
    abnormal_type: str  # LINK_QUALITY_DEGRADE, INTERFACE_FLAP, NEIGHBOR_UNSTABLE
    severity: str = "medium"  # low, medium, high, critical
    created_at: datetime = Field(default_factory=datetime.now)
    evidence: EvidenceModel = Field(default_factory=EvidenceModel)
    state_aggregation: Optional[Dict] = None
    upgrade_check: Optional[Dict] = None


# 研判结果模型
class DiagnosisResult(BaseModel):
    """研判结果模型"""
    task_id: str
    diagnosis_type: str
    confidence: str  # high, medium, low
    problem_type: str  # HARDWARE, CONFIGURATION, LINK, PEER
    summary: str
    details: str
    recommendations: List[str]
    risk_level: str
    auto_executable: bool
    evidence: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)


class DiagnosisService:
    """研判服务"""

    def __init__(self):
        self.llm_client = LLMClient(
            model=settings.llm_model_name,
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_url
        )

    async def create_diagnosis_task(
        self,
        site_id: int,
        netbox_device_id: Optional[int] = None,
        device_ip: Optional[str] = None,
        abnormal_type: str = "UNKNOWN"
    ) -> DiagnosisTask:
        """
        创建研判任务

        Args:
            site_id: 基地ID
            netbox_device_id: 设备ID
            device_ip: 设备IP
            abnormal_type: 异常类型

        Returns:
            研判任务
        """
        task = DiagnosisTask(
            task_id=f"diag_{datetime.now().strftime('%Y%m%d%H%M%S')}_{site_id}",
            site_id=site_id,
            netbox_device_id=netbox_device_id,
            device_ip=device_ip,
            abnormal_type=abnormal_type
        )

        # 执行状态聚合
        task.state_aggregation = state_aggregator.aggregate_device_state(
            site_id=site_id,
            netbox_device_id=netbox_device_id,
            device_ip=device_ip
        )

        # 执行异常升级检查
        task.upgrade_check = abnormal_upgrader.check_upgrade_needed(
            site_id=site_id,
            netbox_device_id=netbox_device_id
        )

        # 构建证据
        task.evidence = await self._build_evidence(task)

        logger.info(f"Created diagnosis task: {task.task_id}")

        return task

    async def diagnose(self, task: DiagnosisTask, use_ai: bool = True) -> DiagnosisResult:
        """
        执行研判

        Args:
            task: 研判任务
            use_ai: 是否使用AI增强

        Returns:
            研判结果
        """
        logger.info(f"Starting diagnosis for task: {task.task_id}")

        try:
            # 步骤1：规则初判
            rule_result = self._rule_pre_check(task)

            # 步骤2：如果有必要，使用AI增强研判
            if use_ai and not rule_result["high_confidence"]:
                ai_result = await self._ai_diagnosis(task)
                result = ai_result
            else:
                result = rule_result["result"]

            logger.info(f"Diagnosis completed for task: {task.task_id}, confidence: {result.confidence}")

            return result

        except Exception as e:
            logger.error(f"Error during diagnosis: {e}", exc_info=True)
            raise e

    async def _build_evidence(self, task: DiagnosisTask) -> EvidenceModel:
        """
        构建证据模型

        Args:
            task: 研判任务

        Returns:
            证据模型
        """
        evidence = EvidenceModel()

        # 日志证据
        if task.state_aggregation and task.state_aggregation.get("has_data"):
            evidence.log_evidence = {
                "crc_trend": task.state_aggregation.get("crc_trend", {}),
                "flap_frequency": task.state_aggregation.get("flap_frequency", {}),
                "neighbor_stability": task.state_aggregation.get("neighbor_stability", {}),
                "summary": task.state_aggregation.get("summary", {})
            }

        # 配置证据（从NetBox获取）
        evidence.config_evidence = await self._get_config_evidence(task)

        # 对端证据（从NetBox获取）
        evidence.peer_evidence = await self._get_peer_evidence(task)

        # 趋势证据
        if task.upgrade_check:
            evidence.trend_evidence = {
                "needs_upgrade": task.upgrade_check.get("needs_upgrade"),
                "abnormal_type": task.upgrade_check.get("abnormal_type"),
                "upgrade_checks": task.upgrade_check.get("upgrade_checks", {})
            }

        return evidence


    async def _get_config_evidence(self, task: DiagnosisTask) -> Dict:
        """
        获取配置证据（从NetBox）

        Args:
            task: 研判任务

        Returns:
            配置证据
        """
        try:
            from mcp.netbox_mcp import NetBoxMCP
            netbox_mcp = NetBoxMCP()
            
            config_evidence = {
                "interface_config": "not_available",
                "qos_config": "not_available",
                "storm_control": "not_available"
            }
            
            # 如果有设备ID，尝试获取设备配置
            if task.netbox_device_id:
                try:
                    result = await netbox_mcp.execute({
                        "action": "get_device_config_by_id",
                        "device_id": task.netbox_device_id
                    })
                    
                    if result.success and result.data:
                        config_data = result.data.get("config", {})
                        config_evidence = {
                            "interface_config": config_data.get("interface_config", "not_configured"),
                            "qos_config": config_data.get("qos_config", "not_configured"),
                            "storm_control": config_data.get("storm_control", "not_configured")
                        }
                except Exception as e:
                    logger.warning(f"Error getting device config from NetBox: {e}")
            
            return config_evidence
            
        except Exception as e:
            logger.error(f"Error getting config evidence: {e}", exc_info=True)
            return {
                "interface_config": "error",
                "qos_config": "error",
                "storm_control": "error"
            }
    
    async def _get_peer_evidence(self, task: DiagnosisTask) -> Dict:
        """
        获取对端证据（从NetBox）

        Args:
            task: 研判任务

        Returns:
            对端证据
        """
        try:
            from mcp.netbox_mcp import NetBoxMCP
            netbox_mcp = NetBoxMCP()
            
            peer_evidence = {
                "peer_device": "not_available",
                "peer_interface": "not_available",
                "peer_errors": "not_available"
            }
            
            # 如果有设备ID，尝试获取设备信息
            if task.netbox_device_id:
                try:
                    result = await netbox_mcp.execute({
                        "action": "query_devices",
                        "id": task.netbox_device_id
                    })
                    
                    if result.success and result.data.get("count", 0) > 0:
                        devices = result.data.get("devices", [])
                        if devices:
                            device = devices[0]
                            peer_evidence = {
                                "peer_device": {
                                    "name": device.get("name"),
                                    "site": device.get("site"),
                                    "role": device.get("role"),
                                    "status": device.get("status")
                                },
                                "peer_interface": "not_available",
                                "peer_errors": "not_available"
                            }
                except Exception as e:
                    logger.warning(f"Error getting device info from NetBox: {e}")
            
            return peer_evidence
            
        except Exception as e:
            logger.error(f"Error getting peer evidence: {e}", exc_info=True)
            return {
                "peer_device": "error",
                "peer_interface": "error",
                "peer_errors": "error"
            }

    def _rule_pre_check(self, task: DiagnosisTask) -> Dict:
        """
        规则初判

        Args:
            task: 研判任务

        Returns:
            规则初判结果
        """
        logger.info(f"Performing rule pre-check for task: {task.task_id}")

        evidence = task.evidence
        result = None
        high_confidence = False

        # 规则1：CRC持续增长 + 无配置策略 → 偏硬件
        if evidence.log_evidence.get("crc_trend", {}).get("trend") == "increasing":
            if evidence.config_evidence.get("storm_control") == "disabled":
                result = DiagnosisResult(
                    task_id=task.task_id,
                    diagnosis_type="RULE_BASED",
                    confidence="high",
                    problem_type="HARDWARE",
                    summary="CRC错误持续增长，配置侧无异常",
                    details="CRC错误呈现上升趋势，且未配置storm-control策略，高度怀疑为光模块或物理链路问题",
                    recommendations=[
                        "检查光模块是否老化或接触不良",
                        "更换光模块或光纤跳线验证",
                        "检查接口物理连接状态"
                    ],
                    risk_level="medium",
                    auto_executable=False,
                    evidence=evidence.dict()
                )
                high_confidence = True

        # 规则2：CRC + storm-control → 偏配置
        elif evidence.log_evidence.get("crc_trend", {}).get("trend") == "increasing":
            if evidence.config_evidence.get("storm_control") == "enabled":
                result = DiagnosisResult(
                    task_id=task.task_id,
                    diagnosis_type="RULE_BASED",
                    confidence="medium",
                    problem_type="CONFIGURATION",
                    summary="CRC错误增长，已配置storm-control",
                    details="CRC错误持续增长，但接口已配置storm-control策略，可能需要调整策略参数或检查链路质量",
                    recommendations=[
                        "检查storm-control参数配置",
                        "评估是否需要调整阈值",
                        "检查链路质量指标"
                    ],
                    risk_level="low",
                    auto_executable=False,
                    evidence=evidence.dict()
                )

        # 规则3：高频flap → 偏链路
        elif evidence.log_evidence.get("flap_frequency", {}).get("frequency") == "high":
            result = DiagnosisResult(
                task_id=task.task_id,
                diagnosis_type="RULE_BASED",
                confidence="medium",
                problem_type="LINK",
                summary="接口高频flap",
                details="接口flap频率过高，可能由于链路不稳定、光纤质量问题或对端设备问题",
                recommendations=[
                    "检查光纤链路质量",
                    "检查对端设备状态",
                    "检查接口配置参数"
                ],
                risk_level="medium",
                auto_executable=False,
                evidence=evidence.dict()
            )

        # 规则4：邻居不稳定 → 偏对端或配置
        elif evidence.log_evidence.get("neighbor_stability", {}).get("stability") == "unstable":
            result = DiagnosisResult(
                task_id=task.task_id,
                diagnosis_type="RULE_BASED",
                confidence="medium",
                problem_type="PEER",
                summary="邻居关系不稳定",
                details="邻居关系频繁变化，可能由于对端设备问题、路由协议配置问题或链路不稳定",
                recommendations=[
                    "检查对端设备状态",
                    "检查路由协议配置",
                    "检查链路稳定性"
                ],
                risk_level="medium",
                auto_executable=False,
                evidence=evidence.dict()
            )

        # 默认结果
        if not result:
            result = DiagnosisResult(
                task_id=task.task_id,
                diagnosis_type="RULE_BASED",
                confidence="low",
                problem_type="UNKNOWN",
                summary="无法通过规则确定问题类型",
                details="当前异常特征不匹配任何已知规则，需要进一步分析",
                recommendations=[
                    "收集更多日志信息",
                    "检查设备配置",
                    "联系网络工程师人工分析"
                ],
                risk_level="low",
                auto_executable=False,
                evidence=evidence.dict()
            )

        return {
            "result": result,
            "high_confidence": high_confidence
        }

    async def _ai_diagnosis(self, task: DiagnosisTask) -> DiagnosisResult:
        """
        AI增强研判

        Args:
            task: 研判任务

        Returns:
            AI研判结果
        """
        logger.info(f"Performing AI diagnosis for task: {task.task_id}")

        # 构建AI提示词
        prompt = self._build_ai_prompt(task)

        # 调用LLM（使用JSON模式）
        try:
            messages = [
                {"role": "system", "content": "你是一位资深的网络运维专家，请根据提供的证据进行研判分析。你必须返回有效的JSON格式。"},
                {"role": "user", "content": prompt}
            ]

            # 使用chat_completion_with_json确保返回JSON格式
            ai_data = await self.llm_client.chat_completion_with_json(
                messages=messages,
                temperature=0.3,
                timeout=60.0,
                max_retries=2
            )

            # 使用model_dump_json自动处理datetime序列化
            evidence_dict = json.loads(task.evidence.model_dump_json())

            result = DiagnosisResult(
                task_id=task.task_id,
                diagnosis_type="AI_ENHANCED",
                confidence=ai_data.get("confidence", "medium"),
                problem_type=ai_data.get("problem_type", "UNKNOWN"),
                summary=ai_data.get("summary", "AI研判完成"),
                details=ai_data.get("details", ""),
                recommendations=ai_data.get("recommendations", []),
                risk_level=ai_data.get("risk_level", "medium"),
                auto_executable=False,
                evidence=evidence_dict
            )

            return result

        except Exception as e:
            logger.error(f"AI diagnosis failed: {e}", exc_info=True)
            # AI失败时返回规则初判结果
            rule_result = self._rule_pre_check(task)
            return rule_result["result"]

    def _build_ai_prompt(self, task: DiagnosisTask) -> str:
        """
        构建AI提示词

        Args:
            task: 研判任务

        Returns:
            AI提示词
        """
        evidence = task.evidence

        prompt = f"""你是一位资深的网络运维专家，请根据以下证据对网络设备问题进行研判。

【异常类型】
{task.abnormal_type}

【日志证据】
- CRC趋势: {evidence.log_evidence.get('crc_trend', {}).get('description', 'N/A')}
- Flap频率: {evidence.log_evidence.get('flap_frequency', {}).get('description', 'N/A')}
- 邻居稳定性: {evidence.log_evidence.get('neighbor_stability', {}).get('description', 'N/A')}

【配置证据】
- 接口配置: {evidence.config_evidence.get('interface_config', 'N/A')}
- QoS配置: {evidence.config_evidence.get('qos_config', 'N/A')}
- Storm Control: {evidence.config_evidence.get('storm_control', 'N/A')}

【对端证据】
- 对端设备: {evidence.peer_evidence.get('peer_device', 'N/A')}
- 对端接口: {evidence.peer_evidence.get('peer_interface', 'N/A')}
- 对端错误: {evidence.peer_evidence.get('peer_errors', 'N/A')}

【趋势证据】
- 是否需要升级: {evidence.trend_evidence.get('needs_upgrade', 'N/A')}
- 异常类型: {evidence.trend_evidence.get('abnormal_type', 'N/A')}

请以JSON格式返回研判结果，包含以下字段：
{{
  "problem_type": "HARDWARE|CONFIGURATION|LINK|PEER",
  "confidence": "high|medium|low",
  "summary": "问题总结（一句话）",
  "details": "详细分析（2-3句话）",
  "recommendations": ["建议1", "建议2", "建议3"],
  "risk_level": "low|medium|high"
}}

注意：
1. 基于证据进行综合判断
2. 给出明确的结论和建议
3. 风险等级要准确反映问题严重性
4. 必须返回有效的JSON格式
"""

        return prompt


# 全局研判服务实例
diagnosis_service = DiagnosisService()
