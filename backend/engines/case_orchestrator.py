from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from adapters.elk_adapter import elk_adapter
from adapters.netbox_adapter import netbox_adapter
from adapters.zabbix_adapter import zabbix_adapter
from agents.alert_triage_agent import alert_triage_agent
from agents.autonomous_remediation_agent import autonomous_remediation_agent
from agents.historical_analysis_agent import historical_analysis_agent
from agents.insight_analysis_agent import insight_analysis_agent
from agents.safety_critic_agent import safety_critic_agent
from agents.schemas import AgentExecutionContext
from config.settings import settings
from harness.contracts import EpisodeGoal, EvidenceQuerySpec, build_evidence_bundle_dict
from pipelines.engine import PipelineEngine
from pipelines.registry import playbook_registry
from pipelines.schemas import PipelineState
from services.automation_settings_service import automation_settings_service
from models.agenticops import (
    AgentClaim,
    AgentRun,
    AgentType,
    CaseRecord,
    CaseStatus,
    EvidenceItem,
    EvidenceType,
    MemoryEntry,
    RemediationPlan,
    RemediationPlanStatus,
    SourceEvent,
    SourceEventStatus,
)
from services.embedding_service import embedding_service
from services.event_decision_service import event_decision_service
from services.memory_ingestion_service import memory_ingestion_service
from services.memory_retriever import memory_retriever
from webhooks.service import webhook_service
from orchestration.agent_runner import agent_runner
from orchestration.context_collector import context_collector
from orchestration.plan_builder import plan_builder
from orchestration.state_finalizer import state_finalizer


class CaseOrchestrator:
    async def intake_case(
        self,
        db: Session,
        *,
        title: str,
        source_type: str,
        source_system: str,
        dedup_key: str,
        severity: str,
        site_id: Optional[int] = None,
        netbox_device_id: Optional[int] = None,
        device_ip: Optional[str] = None,
        host: Optional[str] = None,
        summary: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        raw_payload: Optional[Dict[str, Any]] = None,
        normalized_payload: Optional[Dict[str, Any]] = None,
        case_metadata: Optional[Dict[str, Any]] = None,
    ) -> CaseRecord:
        source_event = db.query(SourceEvent).filter(SourceEvent.dedup_key == dedup_key).first()
        if source_event is None:
            source_event = SourceEvent(
                source_type=source_type,
                source_system=source_system,
                dedup_key=dedup_key,
                site_id=site_id,
                netbox_device_id=netbox_device_id,
                device_ip=device_ip,
                host=host,
                title=title,
                severity=severity,
                occurred_at=occurred_at or datetime.utcnow(),
                raw_payload=raw_payload or {},
                normalized_payload=normalized_payload or {},
                status=SourceEventStatus.CASE_CREATED,
            )
            db.add(source_event)
            db.flush()

        existing_case = (
            db.query(CaseRecord)
            .filter(CaseRecord.source_event_id == source_event.id)
            .order_by(CaseRecord.opened_at.desc())
            .first()
        )
        if existing_case:
            return existing_case

        case_code = f"CASE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{source_event.id}"
        case = CaseRecord(
            case_code=case_code,
            title=title,
            summary=summary,
            source_event_id=source_event.id,
            site_id=site_id,
            netbox_device_id=netbox_device_id,
            device_ip=device_ip,
            host=host,
            risk_level="high" if severity.lower() in {"critical", "high"} else "medium",
            case_metadata=case_metadata or {},
            last_activity_at=datetime.utcnow(),
        )
        db.add(case)
        db.flush()
        webhook_service.enqueue(
            db,
            event_type="case.created",
            aggregate_type="case",
            aggregate_id=str(case.id),
            payload={
                "case_id": int(case.id),
                "case_code": case.case_code,
                "title": case.title,
                "severity": severity,
                "source_system": source_system,
            },
        )

        self._create_evidence(
            db,
            case_id=case.id,
            source_event_id=source_event.id,
            evidence_type=EvidenceType.ALERT,
            source_system=source_system,
            source_ref=dedup_key,
            device_ip=device_ip,
            host=host,
            summary=title,
            payload={
                "title": title,
                "severity": severity,
                "raw_payload": raw_payload or {},
                "normalized_payload": normalized_payload or {},
            },
        )

        self._store_episode_memory(
            db,
            case_id=case.id,
            memory_key=case_code,
            title=title,
            summary=summary or title,
            content={"source_system": source_system, "severity": severity},
        )

        db.commit()
        db.refresh(case)
        return case

    async def run_case_pipeline(
        self,
        db: Session,
        *,
        case_id: int,
        base_name: Optional[str] = None,
        log_query: Optional[str] = None,
        time_range: str = "-15m,now",
        log_limit: int = 200,
        credential_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compatibility entry point: enqueue the durable graph and return acceptance."""
        from orchestration.graph_service import graph_service

        run, already_running = graph_service.enqueue(
            db,
            case_id=case_id,
            input_payload={
                "base_name": base_name,
                "log_query": log_query,
                "time_range": time_range,
                "log_limit": log_limit,
                "credential_id": credential_id,
            },
        )
        return graph_service.view(run, already_running=already_running)

    async def run_legacy_case_pipeline(
        self,
        db: Session,
        *,
        case_id: int,
        base_name: Optional[str] = None,
        log_query: Optional[str] = None,
        time_range: str = "-15m,now",
        log_limit: int = 200,
        credential_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Phase 3 起：把 agent 顺序声明在 pipelines/definitions/*.json，由 PipelineEngine 驱动。
        默认 playbook（pipelines/definitions/default.json）完整复刻先前硬编码顺序。

        返回值新增：
        - playbook_id     —— 实际命中的 playbook 标识
        - pipeline_trace  —— 每个 step / agent / hook / predicate 的执行轨迹
        - critic_decision —— safety critic 判定（pass / soft / rejected）
        """
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).first()
        if case is None:
            raise ValueError("case not found")

        decision_snapshot: Dict[str, Any] = (
            event_decision_service.evaluate_source_event(case.source_event) if case.source_event else {}
        )

        context = AgentExecutionContext(
            case_id=case.id,
            case_code=case.case_code,
            title=case.title,
            summary=case.summary or "",
            source_system=(case.source_event.source_system if case.source_event else "manual"),
            source_payload=(case.source_event.raw_payload if case.source_event else {}),
            normalized_payload=(case.source_event.normalized_payload if case.source_event else {}),
            site_id=case.site_id,
            netbox_device_id=case.netbox_device_id,
            device_ip=case.device_ip,
            host=case.host,
            evidence_items=[],
            prior_claims=[],
            memory_hits=[],
            runtime={},
            evidence_bundle={},
            episode_goal=(case.case_metadata or {}).get("episode_goal") or EpisodeGoal().to_dict(),
            insight_round=0,
            harness_trace=[],
        )

        state = PipelineState(
            db=db,
            case=case,
            context=context,
            extras={
                "base_name": base_name,
                "log_query": log_query,
                "time_range": time_range,
                "log_limit": log_limit,
                "credential_id": credential_id,
                "decision_snapshot": decision_snapshot,
            },
        )

        case_attrs = {
            "source_system": (case.source_event.source_system if case.source_event else "manual"),
            "source_category": decision_snapshot.get("source_category"),
            "signal_family": decision_snapshot.get("signal_family"),
            "severity": (case.source_event.severity if case.source_event else "warning"),
            "priority": case.priority,
            "observe_only": self._is_observe_only(db),
        }
        state.extras["case_attrs"] = case_attrs

        playbook = playbook_registry.select(case_attrs)
        if playbook is None:
            raise RuntimeError("no playbook matched the case; check pipelines/definitions/")

        engine = PipelineEngine(
            agents=self._build_agents_map(),
            hooks=self._build_hooks_map(),
            predicates=self._build_predicates_map(),
            execute_agent_fn=self._execute_agent_for_pipeline,
        )
        await engine.execute(state, playbook)

        return {
            "case_id": case.id,
            "playbook_id": playbook.id,
            "agent_run_ids": [item.id for item in state.runs],
            "claim_ids": [item.id for item in state.claims],
            "remediation_plan_id": state.remediation_plan.id if state.remediation_plan else None,
            "pipeline_trace": state.trace,
            "critic_decision": state.critic_decision,
        }

    async def _collect_runtime_context(
        self,
        db: Session,
        *,
        case: CaseRecord,
        base_name: Optional[str],
        log_query: Optional[str],
        time_range: str,
        log_limit: int,
        credential_id: Optional[int],
    ) -> Dict[str, Any]:
        return await context_collector.collect(
            db,
            case=case,
            base_name=base_name,
            log_query=log_query,
            time_range=time_range,
            log_limit=log_limit,
            credential_id=credential_id,
            evidence_writer=self._create_evidence,
        )

    def _find_similar_closed_cases(self, db: Session, case: CaseRecord, limit: int = 5) -> List[Dict[str, Any]]:
        """Structured case retrieval for Historical agent (RAG-lite, no vectors)."""
        q = (
            db.query(CaseRecord)
            .filter(CaseRecord.id != case.id)
            .filter(CaseRecord.status.in_([CaseStatus.RESOLVED, CaseStatus.CLOSED]))
        )
        if case.site_id is not None:
            q = q.filter(CaseRecord.site_id == case.site_id)
        if case.netbox_device_id is not None:
            q = q.filter(CaseRecord.netbox_device_id == case.netbox_device_id)
        elif case.host:
            q = q.filter(CaseRecord.host == case.host)
        rows = q.order_by(CaseRecord.last_activity_at.desc()).limit(limit).all()
        return [
            {
                "case_id": r.id,
                "case_code": r.case_code,
                "title": r.title,
                "summary": (r.summary or "")[:500],
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            }
            for r in rows
        ]

    async def _supplement_runtime_after_triage(
        self,
        db: Session,
        *,
        case: CaseRecord,
        context: AgentExecutionContext,
        base_name: Optional[str],
        log_query: Optional[str],
        time_range: str,
        log_limit: int,
        credential_id: Optional[int],
        triage_claim: Optional[AgentClaim],
    ) -> None:
        gaps: List[str] = []
        if triage_claim and triage_claim.gaps:
            gaps = [str(g) for g in (triage_claim.gaps or [])]
        joined = " ".join(gaps)
        z = context.runtime.get("zabbix_alerts") or {}
        need_zabbix = "Zabbix" in joined or "zabbix" in joined.lower()
        if need_zabbix and not z.get("success"):
            host = (case.case_metadata or {}).get("zabbix_host") or case.host
            if host:
                zabbix_result = await zabbix_adapter.get_recent_alerts(host=host)
                context.runtime["zabbix_alerts"] = zabbix_result
                if zabbix_result.get("success"):
                    self._create_evidence(
                        db,
                        case_id=case.id,
                        source_event_id=case.source_event_id,
                        evidence_type=EvidenceType.METRIC,
                        source_system="Zabbix",
                        source_ref=host,
                        device_ip=case.device_ip,
                        host=case.host,
                        summary="Zabbix 告警上下文（分诊后补采）",
                        payload={"alerts": zabbix_result.get("alerts", [])},
                    )

        if triage_claim and triage_claim.claim_metadata:
            reqs = triage_claim.claim_metadata.get("next_evidence_requests") or []
            for req in reqs:
                if req.get("type") == "elk_widen_window" and not (context.runtime.get("log_summary") or {}).get("devices"):
                    widened = f"{time_range}" if time_range != "-15m,now" else "-60m,now"
                    logs_result = await elk_adapter.collect_logs(
                        base_name=base_name,
                        query=log_query,
                        time_range=widened,
                        limit=log_limit,
                    )
                    if logs_result.get("success"):
                        context.runtime["log_summary"] = elk_adapter.aggregate_logs(logs_result.get("logs") or [])
                        context.runtime["log_query_widened_to"] = widened

    def _should_second_insight_pass(self, claim: AgentClaim, context: AgentExecutionContext) -> bool:
        if float(claim.confidence or 0) < 0.45:
            return True
        gaps = claim.gaps or []
        if len(gaps) >= 2:
            return True
        if not context.runtime.get("topology") and context.netbox_device_id:
            return True
        return False

    async def _widen_runtime_for_second_insight(
        self,
        db: Session,
        *,
        case: CaseRecord,
        context: AgentExecutionContext,
        base_name: Optional[str],
        log_query: Optional[str],
        credential_id: Optional[int],
    ) -> None:
        logs_result = await elk_adapter.collect_logs(
            base_name=base_name,
            query=log_query,
            time_range="-45m,now",
            limit=400,
        )
        if logs_result.get("success"):
            context.runtime["log_summary"] = elk_adapter.aggregate_logs(logs_result.get("logs") or [])
            context.runtime["insight_second_pass_note"] = "widened_elk_window_-45m"
        if case.netbox_device_id:
            topology_result = await netbox_adapter.get_topology(case.netbox_device_id)
            if topology_result.get("success"):
                context.runtime["topology"] = topology_result.get("data") or {}

    async def _execute_agent(self, db: Session, case: CaseRecord, agent, context: AgentExecutionContext):
        return await agent_runner.execute(db, case, agent, context)

    def _find_memory_hits(
        self,
        db: Session,
        case: CaseRecord,
        runtime: Dict[str, Any],
        *,
        signal_family: str = "",
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Phase 5：委托 memory_retriever 做加权召回（词法 + 元数据 + 可选语义 cosine）。
        query_embedding 由 _hook_collect_runtime_context 在异步上下文里预先算好；
        embedder 关闭时为 None，自动退化为词法 + 元数据召回。
        """
        return memory_retriever.case_memory_hits(
            db,
            case=case,
            runtime=runtime,
            signal_family=signal_family,
            query_embedding=query_embedding,
            task_type="rca",
            limit=5,
        )

    def _load_case_evidence(self, db: Session, case_id: int) -> List[Dict[str, Any]]:
        items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).order_by(EvidenceItem.created_at.asc()).all()
        return [
            {
                "id": item.id,
                "evidence_type": item.evidence_type.value if hasattr(item.evidence_type, "value") else str(item.evidence_type),
                "source_system": item.source_system,
                "summary": item.summary,
                "payload": item.payload or {},
            }
            for item in items
        ]

    def _create_evidence(
        self,
        db: Session,
        *,
        case_id: int,
        source_event_id: Optional[int],
        evidence_type: EvidenceType,
        source_system: str,
        source_ref: Optional[str],
        device_ip: Optional[str],
        host: Optional[str],
        summary: Optional[str],
        payload: Dict[str, Any],
        fingerprint: Optional[str] = None,
    ) -> EvidenceItem:
        evidence = EvidenceItem(
            case_id=case_id,
            source_event_id=source_event_id,
            evidence_type=evidence_type,
            source_system=source_system,
            source_ref=source_ref,
            fingerprint=fingerprint,
            device_ip=device_ip,
            host=host,
            summary=summary,
            payload=payload,
            occurred_at=datetime.utcnow(),
            collected_at=datetime.utcnow(),
        )
        db.add(evidence)
        db.flush()
        return evidence

    def _store_episode_memory(
        self,
        db: Session,
        *,
        case_id: int,
        memory_key: str,
        title: str,
        summary: str,
        content: Dict[str, Any],
    ) -> MemoryEntry:
        entry, _ = memory_ingestion_service.remember_episode(
            db,
            case_id=case_id,
            memory_key=memory_key,
            title=title,
            summary=summary,
            source="case_orchestrator",
            tags=[memory_key, title],
            confidence=0.6,
            success_score=0.0,
            content=content,
        )
        return entry

    def _store_pattern_memories(
        self,
        db: Session,
        case: CaseRecord,
        runtime: Dict[str, Any],
        claims: List[AgentClaim],
    ) -> None:
        log_devices = runtime.get("log_summary", {}).get("devices") or []
        if log_devices:
            top_signature = ((log_devices[0].get("top_signatures") or [{}])[0]).get("signature")
            if top_signature:
                memory_ingestion_service.remember_pattern(
                    db,
                    case_id=case.id,
                    memory_key=f"pattern:{top_signature}",
                    title=f"日志签名模式 {top_signature[:48]}",
                    summary=f"来源于 case {case.case_code} 的高频日志模式",
                    source="pipeline",
                    tags=[case.host or "", case.device_ip or "", "log_signature"],
                    confidence=0.65,
                    success_score=0.0,
                    content={
                        "signature": top_signature,
                        "device": log_devices[0].get("device_ip"),
                        "top_signatures": log_devices[0].get("top_signatures") or [],
                    },
                )

        insight_claims = [item for item in claims if item.claim_type == "root_cause_assessment"]
        insight_claim = max(insight_claims, key=lambda c: float(c.confidence or 0), default=None)
        if insight_claim:
            root_cause = ((insight_claim.agent_run.output_payload or {}).get("root_cause")) or None
            if root_cause:
                key = f"pattern:root_cause:{root_cause}"
                memory_ingestion_service.remember_pattern(
                    db,
                    case_id=case.id,
                    memory_key=key,
                    title=f"根因模式 {root_cause}",
                    summary=insight_claim.claim_text,
                    source="pipeline",
                    tags=[root_cause, case.host or "", case.device_ip or ""],
                    confidence=insight_claim.confidence,
                    success_score=0.0,
                    content=insight_claim.agent_run.output_payload or {},
                )

    def _store_outcome_memory(
        self,
        db: Session,
        case: CaseRecord,
        remediation_plan: RemediationPlan,
        payload: Dict[str, Any],
    ) -> None:
        key = f"outcome:{case.case_code}"
        memory_ingestion_service.remember_outcome(
            db,
            case_id=case.id,
            memory_key=key,
            title=f"修复方案草案 {case.case_code}",
            summary=remediation_plan.summary,
            source="pipeline",
            tags=[case.host or "", case.device_ip or "", remediation_plan.execution_mode],
            confidence=0.6,
            success_score=0.0,
            content={
                "plan_code": remediation_plan.plan_code,
                "execution_mode": remediation_plan.execution_mode,
                "approval_status": remediation_plan.approval_status,
                "recommendations": payload.get("recommendations") or [],
                "root_cause": payload.get("root_cause"),
            },
        )

    def _create_remediation_plan(
        self,
        db: Session,
        case: CaseRecord,
        agent_run: AgentRun,
        claim: AgentClaim,
        payload: Dict[str, Any],
    ) -> RemediationPlan:
        return plan_builder.build(db, case, agent_run, claim, payload)

    @staticmethod
    def _default_verification_policy(case: CaseRecord) -> Dict[str, Any]:
        return plan_builder.default_verification_policy(case)

    def _apply_safety_critic_decision(
        self,
        plan: Optional[RemediationPlan],
        critic_output: Dict[str, Any],
        decision: str,
    ) -> None:
        """
        把 SafetyCriticAgent 的判定写回 RemediationPlan.safety_checks。

        - rejected: 强制 plan 退回 DRAFT、手动模式、必审批；后续 orchestrator 会把 Case 升级到 ESCALATED。
        - soft:    保留 plan 状态，只把 findings 写入 safety_checks 供审批人参考。
        - pass:    仅记录"已通过审查"标记。

        critic_output 来自 SafetyCriticAgent.output_payload，键：
            decision / hard_count / soft_count / findings / rule_codes
        """
        if plan is None:
            return
        safety_checks = dict(plan.safety_checks or {})
        safety_checks["critic_decision"] = decision
        safety_checks["critic_hard_count"] = int(critic_output.get("hard_count") or 0)
        safety_checks["critic_soft_count"] = int(critic_output.get("soft_count") or 0)
        safety_checks["critic_findings"] = critic_output.get("findings") or []
        safety_checks["critic_rule_codes"] = critic_output.get("rule_codes") or []
        plan.safety_checks = safety_checks
        if decision == "rejected":
            plan.status = RemediationPlanStatus.DRAFT
            plan.execution_mode = "manual"
            plan.approval_status = "required"

    # ==================================================================
    # Phase 3 — Pipeline-as-Code 装配：agents / hooks / predicates 字典 +
    # 单步 agent 执行包装 + 每个声明式 step 对应的 Python 钩子。
    # ==================================================================

    def _build_agents_map(self) -> Dict[str, Any]:
        return {
            "alert_triage_agent": alert_triage_agent,
            "historical_analysis_agent": historical_analysis_agent,
            "insight_analysis_agent": insight_analysis_agent,
            "autonomous_remediation_agent": autonomous_remediation_agent,
            "safety_critic_agent": safety_critic_agent,
        }

    def _build_hooks_map(self) -> Dict[str, Any]:
        return {
            "collect_runtime_context": self._hook_collect_runtime_context,
            "supplement_after_triage": self._hook_supplement_after_triage,
            "rebuild_evidence_bundle": self._hook_rebuild_evidence_bundle,
            "find_similar_cases": self._hook_find_similar_cases,
            "widen_runtime_for_second_insight": self._hook_widen_runtime_for_second_insight,
            "create_remediation_plan": self._hook_create_remediation_plan,
            "store_outcome_memory": self._hook_store_outcome_memory,
            "apply_safety_critic": self._hook_apply_safety_critic,
            "store_pattern_memories": self._hook_store_pattern_memories,
            "finalize_case_state": self._hook_finalize_case_state,
        }

    def _build_predicates_map(self) -> Dict[str, Any]:
        return {
            "insight_loop_should_break": self._pred_insight_loop_should_break,
            "should_widen_runtime": self._pred_should_widen_runtime,
        }

    def _is_observe_only(self, db: Session) -> bool:
        try:
            data = automation_settings_service.get_automation_mode(db)
            return bool(data.get("is_observe_only", True))
        except Exception:
            return bool(settings.automation_observe_only)

    # ---- single-agent executor that preserves the original bookkeeping --

    async def _execute_agent_for_pipeline(self, state: PipelineState, agent: Any) -> None:
        agent_type_value = (
            agent.agent_type.value if hasattr(agent.agent_type, "value") else str(agent.agent_type)
        )
        # Insight agent reads context.insight_round to know which round it is in.
        if agent_type_value == AgentType.INSIGHT.value:
            state.context.insight_round = int(state.extras.get("loop_iter", 0))

        run, claim = await self._execute_agent(state.db, state.case, agent, state.context)
        state.runs.append(run)
        state.claims.append(claim)
        state.context.prior_claims.append(
            {
                "id": claim.id,
                "agent_type": claim.agent_type.value if hasattr(claim.agent_type, "value") else str(claim.agent_type),
                "claim_type": claim.claim_type,
                "confidence": claim.confidence,
                "gaps": list(claim.gaps or []),
                "output_payload": run.output_payload or {},
                "metadata": claim.claim_metadata or {},
            }
        )

        if agent_type_value == AgentType.INSIGHT.value:
            tag = f"insight_round_{int(state.extras.get('loop_iter', 0))}_complete"
        else:
            tag_map = {
                AgentType.TRIAGE.value: "triage_complete",
                AgentType.HISTORICAL.value: "historical_complete",
                AgentType.REMEDIATION.value: "remediation_complete",
                AgentType.SAFETY_CRITIC.value: "safety_critic_complete",
            }
            tag = tag_map.get(agent_type_value, f"{agent_type_value}_complete")
        state.context.harness_trace.append(tag)

    # ---- hooks --------------------------------------------------------

    async def _hook_collect_runtime_context(self, state: PipelineState) -> None:
        extras = state.extras
        runtime = await self._collect_runtime_context(
            state.db,
            case=state.case,
            base_name=extras.get("base_name"),
            log_query=extras.get("log_query"),
            time_range=extras.get("time_range") or "-15m,now",
            log_limit=int(extras.get("log_limit") or 200),
            credential_id=extras.get("credential_id"),
        )
        state.context.runtime = runtime
        state.context.evidence_items = self._load_case_evidence(state.db, state.case.id)
        decision_snapshot = extras.get("decision_snapshot") or {}
        signal_family = str(decision_snapshot.get("signal_family") or "")
        # Phase 5: compute the query embedding once (async); None when the embedder is disabled.
        query_text = memory_retriever.build_query_text(case=state.case, signal_family=signal_family)
        try:
            query_embedding = await embedding_service.embed(query_text)
        except Exception:  # noqa: BLE001
            query_embedding = None
        state.context.memory_hits = self._find_memory_hits(
            state.db, state.case, runtime, signal_family=signal_family, query_embedding=query_embedding,
        )

        query_spec = EvidenceQuerySpec(
            elk_base_name=extras.get("base_name"),
            elk_query=extras.get("log_query"),
            elk_time_range=extras.get("time_range") or "-15m,now",
            elk_limit=int(extras.get("log_limit") or 200),
            netbox_device_id=state.case.netbox_device_id,
            zabbix_host=(state.case.case_metadata or {}).get("zabbix_host") or state.case.host,
        )
        state.extras["query_spec"] = query_spec
        state.extras["signal_family"] = signal_family
        state.context.evidence_bundle = build_evidence_bundle_dict(
            case_id=state.case.id,
            case_code=state.case.case_code,
            queries=query_spec,
            evidence_item_ids=[int(x["id"]) for x in state.context.evidence_items if x.get("id") is not None],
            runtime=runtime,
            notes=[f"signal_family={signal_family}" if signal_family else "signal_family=general"],
        )
        state.context.harness_trace.extend(["runtime_collected", "evidence_bundle_built"])

    async def _hook_supplement_after_triage(self, state: PipelineState) -> None:
        extras = state.extras
        triage_claim = state.claims[-1] if state.claims else None
        await self._supplement_runtime_after_triage(
            state.db,
            case=state.case,
            context=state.context,
            base_name=extras.get("base_name"),
            log_query=extras.get("log_query"),
            time_range=extras.get("time_range") or "-15m,now",
            log_limit=int(extras.get("log_limit") or 200),
            credential_id=extras.get("credential_id"),
            triage_claim=triage_claim,
        )

    async def _hook_rebuild_evidence_bundle(self, state: PipelineState) -> None:
        state.context.evidence_items = self._load_case_evidence(state.db, state.case.id)
        query_spec = state.extras.get("query_spec")
        if query_spec is None:
            return
        state.context.evidence_bundle = build_evidence_bundle_dict(
            case_id=state.case.id,
            case_code=state.case.case_code,
            queries=query_spec,
            evidence_item_ids=[int(x["id"]) for x in state.context.evidence_items if x.get("id") is not None],
            runtime=state.context.runtime,
            notes=list((state.context.evidence_bundle or {}).get("notes") or []) + ["post_triage_supplement"],
        )
        state.context.harness_trace.append("post_triage_supplement_done")

    async def _hook_find_similar_cases(self, state: PipelineState) -> None:
        state.context.runtime["similar_cases"] = self._find_similar_closed_cases(state.db, state.case)

    async def _hook_widen_runtime_for_second_insight(self, state: PipelineState) -> None:
        extras = state.extras
        await self._widen_runtime_for_second_insight(
            state.db,
            case=state.case,
            context=state.context,
            base_name=extras.get("base_name"),
            log_query=extras.get("log_query"),
            credential_id=extras.get("credential_id"),
        )
        state.context.evidence_items = self._load_case_evidence(state.db, state.case.id)

    async def _hook_create_remediation_plan(self, state: PipelineState) -> None:
        if not state.claims:
            return
        remediation_claim = state.claims[-1]
        if getattr(remediation_claim, "claim_type", None) != "remediation_strategy":
            return
        run = state.runs[-1]
        state.remediation_plan = self._create_remediation_plan(
            state.db, state.case, run, remediation_claim, run.output_payload or {}
        )

    async def _hook_store_outcome_memory(self, state: PipelineState) -> None:
        if state.remediation_plan is None:
            return
        remediation_claim = next(
            (c for c in reversed(state.claims) if getattr(c, "claim_type", None) == "remediation_strategy"),
            None,
        )
        if remediation_claim is None:
            return
        remediation_run = next(
            (r for r in reversed(state.runs) if getattr(r, "id", None) == getattr(remediation_claim, "agent_run_id", None)),
            state.runs[-1] if state.runs else None,
        )
        if remediation_run is None:
            return
        self._store_outcome_memory(
            state.db, state.case, state.remediation_plan, remediation_run.output_payload or {}
        )

    async def _hook_apply_safety_critic(self, state: PipelineState) -> None:
        if not state.claims:
            return
        critic_claim = state.claims[-1]
        if getattr(critic_claim, "claim_type", None) != "safety_review":
            return
        run = state.runs[-1]
        critic_output = run.output_payload or {}
        decision = str(critic_output.get("decision") or "pass").lower()
        state.critic_decision = decision
        self._apply_safety_critic_decision(state.remediation_plan, critic_output, decision)

    async def _hook_store_pattern_memories(self, state: PipelineState) -> None:
        self._store_pattern_memories(state.db, state.case, state.context.runtime, state.claims)

    async def _hook_finalize_case_state(self, state: PipelineState) -> None:
        state_finalizer.finalize(state)

    # ---- predicates ---------------------------------------------------

    def _pred_insight_loop_should_break(self, state: PipelineState) -> bool:
        if not state.claims:
            return True
        last_claim = state.claims[-1]
        if getattr(last_claim, "claim_type", None) != "root_cause_assessment":
            return True
        iter_idx = int(state.extras.get("loop_iter", 0))
        if iter_idx == 0:
            min_insight = float((state.context.episode_goal or {}).get("min_insight_confidence") or 0.55)
            if float(getattr(last_claim, "confidence", 0) or 0) >= min_insight:
                return True
            if not self._should_second_insight_pass(last_claim, state.context):
                return True
        return False

    def _pred_should_widen_runtime(self, state: PipelineState) -> bool:
        iter_idx = int(state.extras.get("loop_iter", 0))
        if iter_idx != 0:
            return False
        # Only widen if we are NOT about to break the loop after this iteration.
        return not self._pred_insight_loop_should_break(state)


case_orchestrator = CaseOrchestrator()
