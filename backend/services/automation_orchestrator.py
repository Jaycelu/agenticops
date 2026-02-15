"""
自动化编排服务
协调日志采样、状态聚合、异常升级、研判、执行等整个流程
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session

from database import SessionLocal
from models.automation import (
    Site, LogSample, LogAnalysisResult,
    AutomationTask, AutomationPolicy, SSHCredentialDeviceBinding
)
from services.diagnosis_service import diagnosis_service
from services.state_aggregator import state_aggregator
from services.abnormal_upgrader import abnormal_upgrader
from services.execution_engine import execution_engine, ExecutorType
from services.confirmation_service import confirmation_service
from services.approval_service import approval_service
from services.decision_service import decision_service
from services.feedback_learning_service import feedback_learning_service
from services.schemas import SeverityLevel, TaskTriggerEvent, DecisionResult, ExecutionResult as SchemaExecutionResult
from services.context_aware_diagnosis import context_aware_diagnosis_service
from services.site_automation_service import site_automation_service

logger = logging.getLogger(__name__)


class AutomationOrchestrator:
    """自动化编排器"""

    def __init__(self):
        """初始化编排器并注册执行器"""
        self._register_executors()

    def _convert_diagnosis_result(self, diagnosis_result):
        """
        转换diagnosis_service.DiagnosisResult到schemas.DiagnosisResult
        
        Args:
            diagnosis_result: diagnosis_service.DiagnosisResult对象
            
        Returns:
            schemas.DiagnosisResult对象
        """
        from services.schemas import DiagnosisResult as SchemaDiagnosisResult, DiagnosisType, SeverityLevel, Evidence
        
        # 映射diagnosis_type
        diagnosis_type_map = {
            "LINK_QUALITY_DEGRADE": DiagnosisType.LINK_QUALITY_DEGRADE,
            "INTERFACE_FLAP": DiagnosisType.INTERFACE_FLAP,
            "NEIGHBOR_UNSTABLE": DiagnosisType.NEIGHBOR_UNSTABLE,
            "COMBINED_LINK_ISSUE": DiagnosisType.COMBINED_LINK_ISSUE,
            "HIGH_ERROR_RATE": DiagnosisType.HIGH_ERROR_RATE,
            "CONFIGURATION_ISSUE": DiagnosisType.CONFIGURATION_ISSUE,
            "HARDWARE_ISSUE": DiagnosisType.HARDWARE_ISSUE,
            "UNKNOWN": DiagnosisType.UNKNOWN,
            "AI_ENHANCED": DiagnosisType.UNKNOWN  # AI_ENHANCED映射到UNKNOWN
        }
        
        # 映射severity
        severity_map = {
            "low": SeverityLevel.LOW,
            "medium": SeverityLevel.MEDIUM,
            "high": SeverityLevel.HIGH,
            "critical": SeverityLevel.CRITICAL,
            "warning": SeverityLevel.WARNING
        }
        
        # 映射confidence
        confidence_map = {
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2
        }
        
        # 转换diagnosis_type
        diagnosis_type = diagnosis_type_map.get(diagnosis_result.diagnosis_type, DiagnosisType.UNKNOWN)
        
        # 转换severity
        severity = severity_map.get(diagnosis_result.risk_level.lower(), SeverityLevel.MEDIUM)
        
        # 转换confidence
        confidence = confidence_map.get(diagnosis_result.confidence.lower(), 0.5)
        
        # 转换evidence
        evidence = []
        if diagnosis_result.evidence:
            for key, value in diagnosis_result.evidence.items():
                evidence.append(Evidence(
                    type=key,
                    value=value,
                    description=f"{key}证据"
                ))
        
        # 构建SchemaDiagnosisResult
        return SchemaDiagnosisResult(
            diagnosis_type=diagnosis_type,
            severity=severity,
            confidence=confidence,
            summary=diagnosis_result.summary,
            evidence=evidence,
            recommendations=diagnosis_result.recommendations,
            risk_level=severity,
            require_human_confirm=diagnosis_result.risk_level.lower() in ["high", "critical"]
        )

    def _register_executors(self):
        """注册所有执行器到执行引擎"""
        from services.script_executor import script_executor
        from services.api_executor import api_executor
        from services.notification_executor import notification_executor

        execution_engine.register_executor(script_executor)
        execution_engine.register_executor(api_executor)
        execution_engine.register_executor(notification_executor)

        logger.info("All executors registered to execution engine")

    def _severity_rank(self, severity: str) -> int:
        order = {"low": 1, "medium": 2, "warning": 2, "high": 3, "critical": 4}
        return order.get((severity or "").lower(), 1)

    def _build_context_evidence_status(self, context_diag: Dict[str, Any]) -> Dict[str, Any]:
        inspection = (context_diag or {}).get("inspection") or {}
        topology_context = (context_diag or {}).get("topology_context") or {}
        final_result = (context_diag or {}).get("final") or {}
        has_topology = bool((topology_context.get("device") or {}) or (topology_context.get("links") or []))
        inspection_status = inspection.get("status") or "skipped"

        if inspection_status == "success" and has_topology:
            status = "success"
        elif inspection_status == "failed":
            status = "failed"
        elif inspection_status == "manual_required":
            status = "manual_required"
        elif has_topology:
            status = "partial"
        else:
            status = "skipped"

        return {
            "status": status,
            "topology_status": "success" if has_topology else "skipped",
            "inspection_status": inspection_status,
            "final_status": "success" if final_result else "skipped",
            "confidence": final_result.get("confidence"),
            "message": inspection.get("error") or "",
        }

    def _resolve_task_trigger_policy(self, db: Session, site_id: int) -> Dict[str, Any]:
        from config.site_config import get_task_trigger_policy

        site = db.query(Site).filter(Site.id == site_id).first()
        site_code = site.site_code if site else None
        return get_task_trigger_policy(site_code)

    def _evaluate_task_trigger(
        self,
        diagnosis,
        action_type: str,
        inspection_status: str,
        policy: Dict[str, Any]
    ) -> Tuple[bool, bool, str]:
        min_severity = str(policy.get("min_severity", "medium")).lower()
        min_confidence = float(policy.get("min_confidence", 0.6))
        auto_action_types = set(policy.get("auto_action_types", ["config_optimization"]))
        manual_action_types = set(policy.get("manual_action_types", ["replace_hardware", "manual_investigation"]))
        require_inspection_success_for_auto = bool(policy.get("require_inspection_success_for_auto", True))

        risk_obj = getattr(diagnosis, "risk_level", "low")
        risk_level = (risk_obj.value if hasattr(risk_obj, "value") else str(risk_obj)).lower()
        confidence = float(getattr(diagnosis, "confidence", 0.0) or 0.0)
        require_human_confirm = bool(getattr(diagnosis, "require_human_confirm", False))

        if require_human_confirm or action_type in manual_action_types:
            return True, False, "manual_confirmation_required"

        if self._severity_rank(risk_level) < self._severity_rank(min_severity):
            return False, False, f"risk_below_threshold({risk_level}<{min_severity})"

        if confidence < min_confidence:
            return False, False, f"confidence_below_threshold({confidence:.2f}<{min_confidence:.2f})"

        can_auto = action_type in auto_action_types
        if can_auto and require_inspection_success_for_auto and inspection_status != "success":
            can_auto = False

        if can_auto:
            return True, True, "auto_action_allowed"
        return True, False, "task_created_waiting_manual"

    def _attach_context_to_latest_analysis(
        self,
        db: Session,
        sample_id: int,
        context_diag: Dict[str, Any],
        task_trigger_decision: Dict[str, Any]
    ):
        try:
            analysis_result = db.query(LogAnalysisResult).filter(
                LogAnalysisResult.related_sample_id == sample_id
            ).order_by(LogAnalysisResult.created_at.desc()).first()
            if not analysis_result:
                return
            evidence = analysis_result.evidence or {}
            evidence["context_aware"] = context_diag
            evidence["evidence_status"] = self._build_context_evidence_status(context_diag)
            evidence["task_trigger_decision"] = task_trigger_decision
            analysis_result.evidence = evidence
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to attach context evidence for sample {sample_id}: {e}")

    async def process_abnormal_sample(self, sample_id: int):
        """
        处理异常采样，触发研判流程

        Args:
            sample_id: 采样ID
        """
        db = SessionLocal()

        try:
            # 获取采样数据
            sample = db.query(LogSample).filter(LogSample.id == sample_id).first()
            if not sample:
                logger.error(f"Sample not found: {sample_id}")
                return

            if not site_automation_service.is_site_enabled(db, site_id=sample.site_id):
                logger.info(f"Automation disabled for site_id={sample.site_id}, skipping sample {sample_id}")
                return

            if not sample.is_abnormal:
                logger.info(f"Sample {sample_id} is not abnormal, skipping")
                return

            logger.info(f"Processing abnormal sample: {sample_id}, type: {sample.abnormal_type}")

            # 步骤1：执行状态聚合
            state_result = state_aggregator.aggregate_device_state(
                site_id=sample.site_id,
                netbox_device_id=sample.netbox_device_id,
                device_ip=sample.raw_data.get("device_ip") if sample.raw_data else None
            )

            # 步骤2：检查是否需要升级为状态异常
            upgrade_result = abnormal_upgrader.check_upgrade_needed(
                site_id=sample.site_id,
                netbox_device_id=sample.netbox_device_id
            )

            # 步骤3：对异常采样统一执行详细研判
            diagnosis_task = await diagnosis_service.create_diagnosis_task(
                site_id=sample.site_id,
                netbox_device_id=sample.netbox_device_id,
                device_ip=sample.raw_data.get("device_ip") if sample.raw_data else None,
                abnormal_type=sample.abnormal_type
            )

            # 执行研判
            diagnosis_result = await diagnosis_service.diagnose(diagnosis_task)

            # 步骤4：写入分析结果
            self._save_analysis_result(db, sample, diagnosis_result, state_result, upgrade_result)

            logger.info(f"Completed diagnosis for sample {sample_id}: {diagnosis_result.summary}")

            # 步骤5：创建决策任务并执行动作
            await self._create_and_execute_decision_task(
                db, sample, diagnosis_result
            )

        except Exception as e:
            logger.error(f"Error processing abnormal sample {sample_id}: {e}", exc_info=True)
        finally:
            db.close()

    def _save_analysis_result(
        self,
        db: Session,
        sample: LogSample,
        diagnosis_result,
        state_result: Dict,
        upgrade_result: Dict
    ):
        """
        保存分析结果到数据库

        Args:
            db: 数据库会话
            sample: 采样数据
            diagnosis_result: 研判结果
            state_result: 状态聚合结果
            upgrade_result: 升级检查结果
        """
        try:
            # 创建分析结果记录
            analysis_result = LogAnalysisResult(
                site_id=sample.site_id,
                netbox_device_id=sample.netbox_device_id,
                related_sample_id=sample.id,
                analysis_type=diagnosis_result.diagnosis_type,
                confidence=diagnosis_result.confidence,
                summary=diagnosis_result.summary,
                severity=self._map_risk_to_severity(diagnosis_result.risk_level),
                recommendation="\n".join(diagnosis_result.recommendations),
                evidence={
                    "diagnosis": json.loads(diagnosis_result.model_dump_json()),
                    "state_aggregation": state_result,
                    "upgrade_check": upgrade_result
                },
                status="completed"
            )

            db.add(analysis_result)
            db.commit()

            logger.info(f"Saved analysis result for sample {sample.id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error saving analysis result: {e}", exc_info=True)
            raise

    def _map_risk_to_severity(self, risk_level: str) -> str:
        """
        映射风险等级到严重级别

        Args:
            risk_level: 风险等级

        Returns:
            严重级别
        """
        mapping = {
            "low": "info",
            "medium": "warning",
            "high": "critical"
        }
        return mapping.get(risk_level, "info")

    async def check_and_diagnose_all_abnormal_samples(
        self,
        site_id: Optional[int] = None,
        batch_limit: int = 1000
    ):
        """
        检查并诊断所有未处理的异常采样

        Args:
            site_id: 基地ID（可选）
        """
        db = SessionLocal()

        try:
            # 查询需要处理的异常采样
            query = db.query(LogSample).filter(
                LogSample.is_abnormal == True
            )

            if site_id:
                query = query.filter(LogSample.site_id == site_id)

            # 查询未关联分析结果的采样
            analyzed_sample_ids = db.query(LogAnalysisResult.related_sample_id).filter(
                LogAnalysisResult.related_sample_id.isnot(None)
            ).all()
            analyzed_sample_ids = [id[0] for id in analyzed_sample_ids]

            if analyzed_sample_ids:
                query = query.filter(~LogSample.id.in_(analyzed_sample_ids))

            # 按时间排序，批量获取未处理异常采样，避免只处理极少量数据
            samples = query.order_by(LogSample.sampled_at.desc()).limit(max(1, min(batch_limit, 5000))).all()

            logger.info(f"Found {len(samples)} abnormal samples to diagnose")

            # 逐个处理
            for sample in samples:
                await self.process_abnormal_sample(sample.id)

        except Exception as e:
            logger.error(f"Error checking and diagnosing abnormal samples: {e}", exc_info=True)
        finally:
            db.close()

    async def _create_and_execute_decision_task(
        self,
        db: Session,
        sample: LogSample,
        diagnosis_result
    ):
        """
        创建并执行决策任务

        Args:
            db: 数据库会话
            sample: 采样数据
            diagnosis_result: 诊断结果
        """
        try:
            credential_id = None
            if sample.netbox_device_id:
                binding = db.query(SSHCredentialDeviceBinding).filter(
                    SSHCredentialDeviceBinding.netbox_device_id == sample.netbox_device_id
                ).order_by(SSHCredentialDeviceBinding.updated_at.desc()).first()
                if binding:
                    credential_id = binding.credential_id

            context_diag = await context_aware_diagnosis_service.run(
                db=db,
                site_id=sample.site_id,
                netbox_device_id=sample.netbox_device_id,
                abnormal_type=sample.abnormal_type or "UNKNOWN",
                source_logs=sample.raw_data or {},
                credential_id=credential_id,
            )

            # 转换diagnosis_result到schemas.DiagnosisResult格式
            converted_diagnosis = self._convert_diagnosis_result(diagnosis_result)
            converted_diagnosis = feedback_learning_service.calibrate_diagnosis_with_feedback(
                db=db,
                diagnosis=converted_diagnosis,
                site_id=sample.site_id
            )

            final_from_context = context_diag.get("final", {})
            action_type = final_from_context.get("action_type", "")
            inspection_status = (context_diag.get("inspection") or {}).get("status")
            recommendations = final_from_context.get("recommendations")
            if isinstance(recommendations, list) and recommendations:
                converted_diagnosis.recommendations = recommendations
            if final_from_context.get("summary"):
                converted_diagnosis.summary = final_from_context.get("summary")
            if final_from_context.get("severity") in {"low", "medium", "high", "critical"}:
                sev = SeverityLevel(final_from_context.get("severity"))
                converted_diagnosis.severity = sev
                converted_diagnosis.risk_level = sev
            if final_from_context.get("confidence") is not None:
                try:
                    converted_diagnosis.confidence = float(final_from_context.get("confidence"))
                except Exception:
                    pass
            if action_type in {"replace_hardware", "manual_investigation"} or inspection_status == "manual_required":
                converted_diagnosis.require_human_confirm = True

            task_trigger_policy = self._resolve_task_trigger_policy(db, sample.site_id)
            should_create_task, can_auto_execute, trigger_reason = self._evaluate_task_trigger(
                diagnosis=converted_diagnosis,
                action_type=action_type,
                inspection_status=inspection_status or "skipped",
                policy=task_trigger_policy
            )

            task_trigger_decision = {
                "should_create_task": should_create_task,
                "can_auto_execute": can_auto_execute,
                "reason": trigger_reason,
                "policy": task_trigger_policy,
                "action_type": action_type,
                "inspection_status": inspection_status or "skipped",
                "risk_level": converted_diagnosis.risk_level.value if hasattr(converted_diagnosis.risk_level, "value") else str(converted_diagnosis.risk_level),
                "confidence": converted_diagnosis.confidence
            }

            self._attach_context_to_latest_analysis(
                db=db,
                sample_id=sample.id,
                context_diag=context_diag,
                task_trigger_decision=task_trigger_decision
            )

            if not should_create_task:
                logger.info(f"Skip task creation for sample {sample.id}: {trigger_reason}")
                return

            if not can_auto_execute:
                converted_diagnosis.require_human_confirm = True
            
            # 构建决策结果
            decision_result = DecisionResult(
                rule_id=None,
                rule_name="自动诊断规则",
                diagnosis=converted_diagnosis.model_dump(),
                context={
                    "site_id": sample.site_id,
                    "netbox_device_id": sample.netbox_device_id,
                    "device_ip": sample.raw_data.get("device_ip") if sample.raw_data else None,
                    "abnormal_type": sample.abnormal_type,
                    "context_aware": context_diag,
                    "recommended_action_type": action_type,
                    "task_trigger_decision": task_trigger_decision,
                }
            )

            # 构建触发事件
            trigger_event = TaskTriggerEvent(
                event_type="log_sample",
                source_id=sample.id,
                source_type="LogSample",
                data={
                    "site_id": sample.site_id,
                    "netbox_device_id": sample.netbox_device_id,
                    "abnormal_type": sample.abnormal_type
                }
            )

            # 创建决策任务
            task_id = await decision_service.create_decision_task(
                site_id=sample.site_id,
                netbox_device_id=sample.netbox_device_id,
                device_ip=sample.raw_data.get("device_ip") if sample.raw_data else None,
                decision_result=decision_result,
                trigger_event=trigger_event
            )
            if not task_id:
                logger.info(f"Decision task skipped for sample {sample.id} (site automation disabled)")
                return

            logger.info(f"Created decision task {task_id} for sample {sample.id}")

            task_for_audit = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
            if task_for_audit:
                task_for_audit.audit_trail = context_diag.get("audit_trail", [])
                db.commit()

            if not can_auto_execute:
                try:
                    await decision_service.update_task_status(
                        task_id=task_id,
                        status="waiting_confirm",
                        execution_result=SchemaExecutionResult(
                            status="success",
                            message=f"已创建任务，等待人工确认: {trigger_reason}",
                            details={"task_trigger_decision": task_trigger_decision}
                        )
                    )
                except Exception as e:
                    logger.error(f"Error setting waiting_confirm for task {task_id}: {e}", exc_info=True)
                return

            # 查找匹配的策略
            policy = self._find_matching_policy(db, sample.site_id, diagnosis_result)
            logger.debug(
                f"Policy matching for task {task_id}: {policy.policy_code if policy else 'none'}"
            )

            if policy:
                # 重新加载task对象
                task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
                if task:
                    # 执行策略动作
                    await self._execute_policy_action(task, policy)
            else:
                # 重新加载task对象
                task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
                if task:
                    # 没有匹配的策略，只记录诊断结果
                    logger.info(f"No matching policy found for task {task_id}, marking as success")
                    try:
                        await decision_service.update_task_status(
                            task.id,
                            "success",
                            SchemaExecutionResult(
                                status="success",
                                message="诊断完成，未匹配到执行策略",
                                details={"diagnosis": diagnosis_result.model_dump()}
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error updating task status for task {task_id}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error creating and executing decision task: {e}", exc_info=True)

    def _find_matching_policy(
        self,
        db: Session,
        site_id: int,
        diagnosis_result
    ) -> Optional[AutomationPolicy]:
        """
        查找匹配的策略

        Args:
            db: 数据库会话
            site_id: 基地ID
            diagnosis_result: 诊断结果（可能是DiagnosisService的DiagnosisResult或schemas的DiagnosisResult）

        Returns:
            匹配的策略
        """
        try:
            # 查询基地的启用策略
            policies = db.query(AutomationPolicy).filter(
                AutomationPolicy.site_id == site_id,
                AutomationPolicy.enabled == True
            ).all()

            logger.info(f"Found {len(policies)} enabled policies for site_id {site_id}")

            # 获取诊断类型（兼容两种不同的DiagnosisResult模型）
            diagnosis_type = None
            if hasattr(diagnosis_result, 'diagnosis_type'):
                # 如果是枚举类型，获取其value
                if hasattr(diagnosis_result.diagnosis_type, 'value'):
                    diagnosis_type = diagnosis_result.diagnosis_type.value
                else:
                    # 如果是字符串类型，直接使用
                    diagnosis_type = diagnosis_result.diagnosis_type

            logger.info(f"Extracted diagnosis_type: {diagnosis_type} (type: {type(diagnosis_result).__name__})")

            if not diagnosis_type:
                logger.warning(f"Cannot extract diagnosis_type from diagnosis_result")
                return None

            # 简单匹配逻辑：根据诊断类型匹配
            for policy in policies:
                trigger_condition = policy.trigger_condition or {}
                policy_diagnosis_type = trigger_condition.get("diagnosis_type")
                logger.info(f"Checking policy {policy.policy_code}: policy_diagnosis_type={policy_diagnosis_type}, diagnosis_type={diagnosis_type}, match={policy_diagnosis_type == diagnosis_type}")
                if policy_diagnosis_type == diagnosis_type:
                    logger.info(f"Matched policy {policy.policy_code} for diagnosis_type {diagnosis_type}")
                    return policy

            logger.info(f"No matching policy found for diagnosis_type {diagnosis_type}")
            return None

        except Exception as e:
            logger.error(f"Error finding matching policy: {e}", exc_info=True)
            return None

    async def _execute_policy_action(
        self,
        task: AutomationTask,
        policy: AutomationPolicy
    ):
        """
        执行策略动作

        Args:
            task: 任务
            policy: 策略
        """
        try:
            action = policy.action
            if not action:
                logger.warning(f"Policy {policy.id} has no action defined")
                return

            action_type_str = action.get("type")
            action_config = action.get("config", {})

            # 映射动作类型
            action_type_mapping = {
                "script": ExecutorType.SCRIPT,
                "api": ExecutorType.API,
                "notification": ExecutorType.NOTIFICATION
            }

            action_type = action_type_mapping.get(action_type_str)
            if not action_type:
                logger.error(f"Unknown action type: {action_type_str}")
                return

            # 检查是否需要确认
            requires_confirm, reason, confirmation_info = confirmation_service.requires_confirmation(
                task.id,
                action_type,
                action_config,
                diagnosis_risk_level=task.decision_result.get("diagnosis", {}).get("risk_level")
            )

            if requires_confirm:
                logger.info(f"Task {task.id} requires confirmation: {reason}")

                # 请求确认
                await confirmation_service.request_confirmation(task.id, confirmation_info)

                # 更新任务状态
                await decision_service.update_task_status(
                    task.id,
                    "waiting_confirm",
                    None
                )
                return

            # 检查是否需要审批
            risk_level = task.decision_result.get("diagnosis", {}).get("risk_level", "medium")
            approval_level = approval_service.get_approval_level(risk_level)

            if approval_level:
                logger.info(f"Task {task.id} requires approval level: {approval_level}")

                # 发起审批流程
                await approval_service.initiate_approval(
                    task.id,
                    risk_level,
                    "system"
                )

                # 更新任务状态
                await decision_service.update_task_status(
                    task.id,
                    "waiting_approval",
                    None
                )
                return

            # 执行动作
            logger.info(f"Executing action for task {task.id}: {action_type}")

            # 构建上下文
            context = {
                "task_id": task.id,
                "task_code": task.task_code,
                "site_id": task.site_id,
                "netbox_device_id": task.netbox_device_id,
                "decision_result": task.decision_result,
                "policy_id": policy.id,
                "policy_name": policy.policy_name
            }

            # 执行动作
            execution_result = await execution_engine.execute_action(
                task.id,
                action_type,
                action_config,
                context
            )

            # 更新任务状态
            status = "success" if execution_result.is_success() else "failed"
            await decision_service.update_task_status(
                task.id,
                status,
                execution_result
            )

            logger.info(f"Task {task.id} execution completed with status: {status}")

        except Exception as e:
            logger.error(f"Error executing policy action for task {task.id}: {e}", exc_info=True)

            # 更新任务状态为失败
            await decision_service.update_task_status(
                task.id,
                "failed",
                SchemaExecutionResult(
                    status="failed",
                    message=f"执行失败: {str(e)}",
                    details={"error": str(e)}
                )
            )

    async def process_pending_tasks(self, site_id: Optional[int] = None):
        """
        处理待执行的任务

        Args:
            site_id: 基地ID（可选）
        """
        try:
            # 获取待执行的任务
            tasks = await decision_service.get_pending_tasks(site_id)

            logger.info(f"Found {len(tasks)} pending tasks to execute")

            for task in tasks:
                try:
                    db = SessionLocal()
                    try:
                        if not site_automation_service.is_site_enabled(db, site_id=task.site_id):
                            logger.info(f"Skip task {task.id} because automation is disabled for site_id={task.site_id}")
                            continue
                    finally:
                        db.close()

                    # 重新加载策略并执行
                    db = SessionLocal()
                    try:
                        # 如果policy_id为None，直接标记为成功（诊断完成，无需执行策略）
                        if task.policy_id is None:
                            logger.info(f"Task {task.id} has no policy, marking as success")
                            await decision_service.update_task_status(
                                task.id,
                                "success",
                                SchemaExecutionResult(
                                    status="success",
                                    message="诊断完成，未配置执行策略",
                                    details={"task_id": task.id}
                                )
                            )
                            continue

                        # 查找策略
                        policy = db.query(AutomationPolicy).filter(
                            AutomationPolicy.id == task.policy_id
                        ).first()

                        if policy:
                            await self._execute_policy_action(task, policy)
                        else:
                            logger.warning(f"Policy {task.policy_id} not found for task {task.id}")
                            # 策略不存在，标记为成功
                            await decision_service.update_task_status(
                                task.id,
                                "success",
                                SchemaExecutionResult(
                                    status="success",
                                    message="诊断完成，策略不存在",
                                    details={"task_id": task.id, "policy_id": task.policy_id}
                                )
                            )

                    finally:
                        db.close()

                except Exception as e:
                    logger.error(f"Error processing task {task.id}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error processing pending tasks: {e}", exc_info=True)


# 全局自动化编排器实例
automation_orchestrator = AutomationOrchestrator()
