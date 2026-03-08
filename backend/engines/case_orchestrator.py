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
from agents.schemas import AgentExecutionContext
from models.agenticops import (
    AgentClaim,
    AgentRun,
    AgentRunStatus,
    AgentType,
    CaseRecord,
    CaseStatus,
    ClaimStatus,
    EvidenceItem,
    EvidenceType,
    MemoryEntry,
    MemoryType,
    RemediationPlan,
    RemediationPlanStatus,
    SourceEvent,
    SourceEventStatus,
)
from services.memory_ingestion_service import memory_ingestion_service


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
        case = db.query(CaseRecord).filter(CaseRecord.id == case_id).first()
        if case is None:
            raise ValueError("case not found")

        runtime = await self._collect_runtime_context(
            db,
            case=case,
            base_name=base_name,
            log_query=log_query,
            time_range=time_range,
            log_limit=log_limit,
            credential_id=credential_id,
        )
        evidence_items = self._load_case_evidence(db, case.id)
        memory_hits = self._find_memory_hits(db, case, runtime)
        prior_claims: List[Dict[str, Any]] = []
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
            evidence_items=evidence_items,
            prior_claims=prior_claims,
            memory_hits=memory_hits,
            runtime=runtime,
        )

        agents = [
            alert_triage_agent,
            historical_analysis_agent,
            insight_analysis_agent,
            autonomous_remediation_agent,
        ]

        runs: List[AgentRun] = []
        claims: List[AgentClaim] = []
        for agent in agents:
            run, claim = await self._execute_agent(db, case, agent, context)
            runs.append(run)
            claims.append(claim)
            prior_claims.append(
                {
                    "id": claim.id,
                    "agent_type": claim.agent_type.value if hasattr(claim.agent_type, "value") else str(claim.agent_type),
                    "claim_type": claim.claim_type,
                    "confidence": claim.confidence,
                    "output_payload": run.output_payload or {},
                    "metadata": claim.claim_metadata or {},
                }
            )
            context.prior_claims = prior_claims

        remediation_claim = claims[-1] if claims else None
        remediation_plan = None
        if remediation_claim:
            remediation_plan = self._create_remediation_plan(db, case, runs[-1], remediation_claim, runs[-1].output_payload or {})
            self._store_outcome_memory(db, case, remediation_plan, runs[-1].output_payload or {})

        self._store_pattern_memories(db, case, runtime, claims)

        case.status = CaseStatus.PLANNED if remediation_plan else CaseStatus.INVESTIGATING
        case.current_phase = "remediation_draft" if remediation_plan else "analysis"
        case.last_activity_at = datetime.utcnow()
        db.commit()
        db.refresh(case)

        return {
            "case_id": case.id,
            "agent_run_ids": [item.id for item in runs],
            "claim_ids": [item.id for item in claims],
            "remediation_plan_id": remediation_plan.id if remediation_plan else None,
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
        runtime: Dict[str, Any] = {}

        logs_result = await elk_adapter.collect_logs(
            base_name=base_name,
            query=log_query,
            time_range=time_range,
            limit=log_limit,
        )
        if logs_result.get("success"):
            runtime["log_summary"] = elk_adapter.aggregate_logs(logs_result.get("logs") or [])
            self._create_evidence(
                db,
                case_id=case.id,
                source_event_id=case.source_event_id,
                evidence_type=EvidenceType.LOG,
                source_system="ELK",
                source_ref=base_name or log_query or "*",
                device_ip=case.device_ip,
                host=case.host,
                summary="ELK 日志聚合摘要",
                payload=runtime["log_summary"],
                fingerprint=(runtime["log_summary"].get("devices") or [{}])[0].get("top_signatures", [{}])[0].get("signature"),
            )

        if case.netbox_device_id:
            device_result = await netbox_adapter.get_device(case.netbox_device_id)
            topology_result = await netbox_adapter.get_topology(case.netbox_device_id)
            if device_result.get("success"):
                runtime["device"] = device_result.get("data") or {}
                self._create_evidence(
                    db,
                    case_id=case.id,
                    source_event_id=case.source_event_id,
                    evidence_type=EvidenceType.TOPOLOGY,
                    source_system="NetBox",
                    source_ref=str(case.netbox_device_id),
                    device_ip=case.device_ip,
                    host=case.host,
                    summary="NetBox 设备上下文",
                    payload=runtime["device"],
                )
            if topology_result.get("success"):
                runtime["topology"] = topology_result.get("data") or {}

            # SSH 已从默认诊断链路降级为执行/人工维护通道，不再自动采集现场证据。
            runtime["ssh_result"] = {
                "success": False,
                "skipped": True,
                "reason": "ssh_demoted_to_execution_channel",
                "credential_id": credential_id,
            }

        if (case.source_event and case.source_event.source_system.lower() == "zabbix") or (
            case.case_metadata or {}
        ).get("zabbix_host"):
            host = (case.case_metadata or {}).get("zabbix_host") or case.host
            zabbix_result = await zabbix_adapter.get_recent_alerts(host=host)
            runtime["zabbix_alerts"] = zabbix_result
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
                    summary="Zabbix 告警上下文",
                    payload={"alerts": zabbix_result.get("alerts", [])},
                )

        return runtime

    async def _execute_agent(self, db: Session, case: CaseRecord, agent, context: AgentExecutionContext):
        started_at = datetime.utcnow()
        run = AgentRun(
            case_id=case.id,
            agent_type=agent.agent_type,
            agent_name=agent.agent_name,
            status=AgentRunStatus.RUNNING,
            input_payload={
                "case_id": case.id,
                "evidence_count": len(context.evidence_items),
                "memory_hits": len(context.memory_hits),
            },
            started_at=started_at,
        )
        db.add(run)
        db.flush()

        try:
            decision = await agent.run(context)
            finished_at = datetime.utcnow()
            run.status = AgentRunStatus.COMPLETED
            run.finished_at = finished_at
            run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            run.output_payload = decision.output_payload

            claim = AgentClaim(
                case_id=case.id,
                agent_run_id=run.id,
                agent_type=agent.agent_type,
                claim_type=decision.claim_type,
                claim_text=decision.claim_text,
                status=ClaimStatus(decision.status),
                confidence=decision.confidence,
                evidence_refs=decision.evidence_refs,
                gaps=decision.gaps,
                claim_metadata=decision.metadata,
            )
            db.add(claim)
            db.flush()
            return run, claim
        except Exception as exc:  # noqa: BLE001
            finished_at = datetime.utcnow()
            run.status = AgentRunStatus.FAILED
            run.finished_at = finished_at
            run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            run.error_message = str(exc)
            claim = AgentClaim(
                case_id=case.id,
                agent_run_id=run.id,
                agent_type=agent.agent_type,
                claim_type="agent_failure",
                claim_text=f"{agent.agent_name} 执行失败: {exc}",
                status=ClaimStatus.REJECTED,
                confidence=0.0,
                evidence_refs=[],
                gaps=[str(exc)],
                claim_metadata={},
            )
            db.add(claim)
            db.flush()
            return run, claim

    def _find_memory_hits(self, db: Session, case: CaseRecord, runtime: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = (
            db.query(MemoryEntry)
            .filter((MemoryEntry.case_id.is_(None)) | (MemoryEntry.case_id != case.id))
            .order_by(MemoryEntry.confidence.desc(), MemoryEntry.created_at.desc())
        )
        candidates = query.limit(20).all()
        tokens = {case.device_ip or "", case.host or "", case.title.lower()}
        log_devices = runtime.get("log_summary", {}).get("devices") or []
        if log_devices:
            tokens.add(log_devices[0].get("device_ip") or "")
        matched = []
        for item in candidates:
            haystack = " ".join(
                [
                    item.memory_key or "",
                    item.title or "",
                    item.summary or "",
                    " ".join(item.tags or []),
                ]
            ).lower()
            if any(token and token.lower() in haystack for token in tokens):
                matched.append(
                    {
                        "id": item.id,
                        "memory_type": item.memory_type.value if hasattr(item.memory_type, "value") else str(item.memory_type),
                        "title": item.title,
                        "summary": item.summary,
                        "confidence": item.confidence,
                        "success_score": item.success_score,
                        "content": item.content or {},
                    }
                )
        return matched[:5]

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

        insight_claim = next((item for item in claims if item.claim_type == "root_cause_assessment"), None)
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
        plan = (
            db.query(RemediationPlan)
            .filter(RemediationPlan.case_id == case.id)
            .order_by(RemediationPlan.created_at.desc())
            .first()
        )
        if plan is None:
            plan = RemediationPlan(
                case_id=case.id,
                plan_code=f"PLAN-{case.case_code}",
            )
            db.add(plan)
            db.flush()

        plan.generated_by_agent_run_id = agent_run.id
        plan.status = RemediationPlanStatus.DRAFT
        plan.execution_mode = payload.get("execution_mode") or "manual"
        plan.approval_status = payload.get("approval_status") or "required"
        plan.risk_level = case.risk_level
        plan.summary = claim.claim_text
        plan.plan_payload = {
            "recommendations": payload.get("recommendations") or [],
            "recommended_actions": payload.get("recommended_actions") or [],
            "root_cause": payload.get("root_cause"),
            "impact_scope": payload.get("impact_scope"),
        }
        plan.rollback_payload = {"steps": payload.get("rollback_plan") or []}
        plan.safety_checks = payload.get("safety_checks") or {}
        return plan


case_orchestrator = CaseOrchestrator()
