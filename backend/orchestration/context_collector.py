from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from adapters.elk_adapter import elk_adapter
from adapters.netbox_adapter import netbox_adapter
from adapters.ssh_adapter import ssh_adapter
from adapters.zabbix_adapter import zabbix_adapter
from models.agenticops import CaseRecord, EvidenceType
from probes.gateway import probe_gateway
from probes.schemas import ProbeRequest


class ContextCollector:
    async def collect(
        self,
        db: Session,
        *,
        case: CaseRecord,
        base_name: str | None,
        log_query: str | None,
        time_range: str,
        log_limit: int,
        credential_id: int | None,
        evidence_writer: Callable[..., Any],
    ) -> dict[str, Any]:
        runtime: dict[str, Any] = {}
        logs_result = await elk_adapter.collect_logs(
            base_name=base_name, query=log_query, time_range=time_range, limit=log_limit
        )
        if logs_result.get("success"):
            runtime["log_summary"] = elk_adapter.aggregate_logs(logs_result.get("logs") or [])
            evidence_writer(
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
                fingerprint=(runtime["log_summary"].get("devices") or [{}])[0]
                .get("top_signatures", [{}])[0]
                .get("signature"),
            )
        if case.netbox_device_id:
            device_result = await netbox_adapter.get_device(case.netbox_device_id)
            topology_result = await netbox_adapter.get_topology(case.netbox_device_id)
            if device_result.get("success"):
                runtime["device"] = device_result.get("data") or {}
                evidence_writer(
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
            effective_credential_id = credential_id or ssh_adapter.resolve_credential_id(db, case.netbox_device_id)
            if effective_credential_id:
                result = probe_gateway.run(
                    db,
                    ProbeRequest(
                        probe_id="network.system_status",
                        netbox_device_id=case.netbox_device_id,
                        credential_id=effective_credential_id,
                    ),
                )
                runtime["ssh_result"] = result.model_dump(mode="json")
                if result.evidence:
                    evidence_writer(
                        db,
                        case_id=case.id,
                        source_event_id=case.source_event_id,
                        evidence_type=EvidenceType.COMMAND_OUTPUT,
                        source_system="ProbeGateway",
                        source_ref=str(result.run_id),
                        device_ip=case.device_ip,
                        host=case.host,
                        summary="只读设备基础状态",
                        payload=result.evidence.model_dump(mode="json"),
                    )
            else:
                runtime["ssh_result"] = {
                    "success": False,
                    "skipped": True,
                    "reason": "missing_read_only_ssh_binding",
                }
        if (case.source_event and case.source_event.source_system.lower() == "zabbix") or (
            case.case_metadata or {}
        ).get("zabbix_host"):
            host = (case.case_metadata or {}).get("zabbix_host") or case.host
            result = await zabbix_adapter.get_recent_alerts(host=host)
            runtime["zabbix_alerts"] = result
            if result.get("success"):
                evidence_writer(
                    db,
                    case_id=case.id,
                    source_event_id=case.source_event_id,
                    evidence_type=EvidenceType.METRIC,
                    source_system="Zabbix",
                    source_ref=host,
                    device_ip=case.device_ip,
                    host=case.host,
                    summary="Zabbix 告警上下文",
                    payload={"alerts": result.get("alerts", [])},
                )
        return runtime


context_collector = ContextCollector()
