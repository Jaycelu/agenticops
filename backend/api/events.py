import hashlib
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.common import MessageResponse, PageMeta
from api.schemas.events import (
    EventClusterListResponse,
    EventDispositionRequest,
    EventDispatchRequest,
    EventDispatchResponse,
    EventIngestRequest,
    EventIngestResponse,
    EventListResponse,
    EventPlaybookDraftRequest,
    EventPlaybookDraftResponse,
    EventRelationsResponse,
    RootCauseCandidateListResponse,
    EventTicketCreateRequest,
    EventTicketResponse,
)
from config.settings import settings
from database import get_db
from engines.case_orchestrator import case_orchestrator
from adapters.netbox_adapter import netbox_adapter
from models.agenticops import ExecutionRun, RemediationPlan, SourceEvent, SourceEventStatus
from models.automation import AssetDevice, LocalTicket, Site
from services.playbook_draft_service import playbook_draft_service
from services.event_decision_service import event_decision_service
from services.remediation_recommendation_service import remediation_recommendation_service
from services.source_event_projection import attach_event_projection, build_event_shadow, upsert_source_event
from services.ticket_adapter import ticket_adapter

router = APIRouter(prefix="/api/events", tags=["events"])
_UNSET = object()

def _source_event_event_status(item: SourceEvent, payload: Dict[str, Any]) -> str:
    legacy_status = payload.get("legacy_status")
    if legacy_status:
        return str(legacy_status)
    value = item.status.value if hasattr(item.status, "value") else str(item.status)
    mapping = {
        "new": "open",
        "correlated": "acknowledged",
        "case_created": "acknowledged",
        "closed": "resolved",
    }
    return mapping.get(value, "open")


def _serialize_source_event(item: SourceEvent) -> Dict[str, Any]:
    payload = dict(item.normalized_payload or {})
    payload.setdefault("raw", item.raw_payload or {})
    case_info = event_decision_service.get_case_info(payload)
    decision = event_decision_service.evaluate_source_event(item)
    legacy_last_seen_at = payload.get("legacy_last_seen_at")
    legacy_resolved_at = payload.get("legacy_resolved_at")
    legacy_event_id = payload.get("legacy_event_id")
    event_status = _source_event_event_status(item, payload)
    return {
        "id": int(legacy_event_id or item.legacy_event_id or item.id),
        "source_event_id": int(item.id),
        "source": item.source_system,
        "source_label": event_decision_service.get_source_label(item.source_system, payload),
        "source_category": event_decision_service.get_source_category(item.source_system, payload),
        "event_type": payload.get("event_type") or item.source_type or "unknown",
        "signal_key": payload.get("signal_key"),
        "disposition": decision.get("disposition"),
        "disposition_reason": decision.get("reason"),
        "decision_confidence": decision.get("confidence"),
        "cluster_key": decision.get("cluster_key"),
        "correlation_key": decision.get("correlation_key"),
        "signal_family": decision.get("signal_family"),
        "external_event_id": item.external_event_id,
        "dedup_key": item.dedup_key,
        "site_id": item.site_id,
        "netbox_device_id": item.netbox_device_id,
        "host": item.host,
        "name": item.title,
        "severity": item.severity,
        "severity_level": int(payload.get("severity_level") or 0),
        "status": event_status,
        "acknowledged": bool(payload.get("legacy_acknowledged") or event_status != "open"),
        "occurred_at": item.occurred_at,
        "resolved_at": _parse_optional_datetime(legacy_resolved_at),
        "last_seen_at": _parse_optional_datetime(legacy_last_seen_at) or item.collected_at,
        "payload": payload,
        "case_id": case_info.get("case_id"),
        "case_code": case_info.get("case_code"),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _infer_topology_hint(
    *,
    signal_family: Optional[str],
    source_categories: set[str],
    device_role: Optional[str],
) -> str:
    family = str(signal_family or "").lower()
    role = str(device_role or "").lower()
    cross_source = "log_signal" in source_categories and "zabbix_alert" in source_categories

    if family in {"neighbor", "routing", "ospf", "bgp"}:
        return "建议结合 NetBox 拓扑查看邻接设备、路由邻居和上联链路。"
    if family in {"crc", "interface", "flap", "link"}:
        return "优先检查 NetBox 拓扑中的上下联链路、对端口和物理连接关系。"
    if "core" in role or "spine" in role:
        return "核心角色设备发生异常，建议优先查看其下游关联设备与关键链路影响面。"
    if "access" in role or "edge" in role:
        return "接入侧异常，建议沿 NetBox 上联链路回溯到汇聚或核心设备。"
    if cross_source:
        return "日志与监控已形成跨源确认，可优先按该设备在 NetBox 中的上下游关系排查。"
    return "建议结合 NetBox 设备角色和站点归属补充拓扑上下文。"


def _infer_root_cause_candidate(
    *,
    signal_family: Optional[str],
    source_categories: set[str],
    device_role: Optional[str],
) -> str:
    family = str(signal_family or "").lower()
    role = str(device_role or "").lower()
    cross_source = "log_signal" in source_categories and "zabbix_alert" in source_categories

    if family in {"crc", "interface", "flap", "link"}:
        return "链路或接口层异常"
    if family in {"neighbor", "routing", "ospf", "bgp"}:
        return "邻居关系或路由稳定性异常"
    if family in {"hardware", "fan", "power", "temperature"}:
        return "硬件或光模块异常"
    if family in {"auth", "security"}:
        return "认证或安全策略异常"
    if cross_source and ("core" in role or "spine" in role):
        return "核心节点跨源确认故障"
    if cross_source:
        return "跨源确认的设备异常"
    return "待进一步研判的设备异常"


def _aggregate_clusters(records: list[Dict[str, Any]], db: Session) -> list[Dict[str, Any]]:
    severity_order = {
        "critical": 5,
        "high": 4,
        "major": 3,
        "warning": 2,
        "medium": 2,
        "low": 1,
        "info": 1,
    }
    device_ids = sorted({item.netbox_device_id for item in records if item.netbox_device_id})
    site_ids = sorted({item.site_id for item in records if item.site_id})
    asset_map: Dict[int, AssetDevice] = {}
    site_map: Dict[int, Site] = {}
    if device_ids:
        asset_map = {
            item.netbox_device_id: item
            for item in db.query(AssetDevice).filter(AssetDevice.netbox_device_id.in_(device_ids)).all()
        }
    if site_ids:
        site_map = {
            item.id: item
            for item in db.query(Site).filter(Site.id.in_(site_ids)).all()
        }

    clusters: Dict[str, Dict[str, Any]] = {}
    for record in records:
        asset = asset_map.get(record.get("netbox_device_id")) if record.get("netbox_device_id") else None
        site = site_map.get(record.get("site_id")) if record.get("site_id") else None
        cluster_key = str(record.get("correlation_key") or record.get("cluster_key") or f"event:{record.get('id')}")
        item = clusters.setdefault(
            cluster_key,
            {
                "cluster_key": record.get("cluster_key") or cluster_key,
                "correlation_key": cluster_key,
                "title": record.get("name"),
                "event_count": 0,
                "source_categories": set(),
                "dispositions": {},
                "case_count": 0,
                "ticket_count": 0,
                "highest_severity": record.get("severity"),
                "severity_level": severity_order.get(str(record.get("severity", "warning")).lower(), 2),
                "host": record.get("host"),
                "site_id": record.get("site_id"),
                "netbox_device_id": record.get("netbox_device_id"),
                "latest_occurred_at": record.get("occurred_at"),
                "signal_family": record.get("signal_family"),
                "device_name": asset.name if asset else None,
                "device_role": asset.role if asset else None,
                "site_name": (asset.site if asset and asset.site else None) or (site.site_name if site else None),
            },
        )
        item["event_count"] += 1
        source_category = str(record.get("source_category") or "external_event")
        item["source_categories"].add(source_category)
        disposition = record.get("disposition") or "ticket_only"
        item["dispositions"][disposition] = item["dispositions"].get(disposition, 0) + 1
        if record.get("case_id"):
            item["case_count"] += 1
        if ((record.get("payload") or {}).get("ticket") or {}).get("ticket_id"):
            item["ticket_count"] += 1

        current_severity = severity_order.get(str(record.get("severity")).lower(), 2)
        if current_severity > item["severity_level"]:
            item["severity_level"] = current_severity
            item["highest_severity"] = record.get("severity")
            item["title"] = record.get("name")

        occurred_at = record.get("occurred_at")
        if occurred_at and (item["latest_occurred_at"] is None or occurred_at > item["latest_occurred_at"]):
            item["latest_occurred_at"] = occurred_at

    return sorted(
        [
            {
                **item,
                "source_categories": sorted(item["source_categories"]),
                "topology_hint": _infer_topology_hint(
                    signal_family=item.get("signal_family"),
                    source_categories=item.get("source_categories", set()),
                    device_role=item.get("device_role"),
                ),
                "root_cause_candidate": _infer_root_cause_candidate(
                    signal_family=item.get("signal_family"),
                    source_categories=item.get("source_categories", set()),
                    device_role=item.get("device_role"),
                ),
            }
            for item in clusters.values()
        ],
        key=lambda value: (
            value["event_count"],
            value["case_count"],
            severity_order.get(str(value["highest_severity"]).lower(), 2),
        ),
        reverse=True,
    )


async def _enrich_clusters_with_topology(clusters: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    enriched: list[Dict[str, Any]] = []
    for cluster in clusters:
        netbox_device_id = cluster.get("netbox_device_id")
        if not netbox_device_id:
            cluster["adjacent_devices"] = []
            cluster["link_count"] = 0
            cluster["impact_scope"] = "site_scope"
            enriched.append(cluster)
            continue

        try:
            topology_result = await netbox_adapter.get_topology(int(netbox_device_id))
        except Exception:
            topology_result = {"success": False, "data": {}, "error": "topology_lookup_failed"}

        if not topology_result.get("success"):
            cluster["adjacent_devices"] = []
            cluster["link_count"] = 0
            cluster["impact_scope"] = "device_scope"
            enriched.append(cluster)
            continue

        topology = topology_result.get("data") or {}
        links = topology.get("links") or []
        adjacent_devices = sorted(
            {
                str(link.get("peer_device")).strip()
                for link in links
                if str(link.get("peer_device") or "").strip()
            }
        )
        link_count = int(topology.get("link_count") or len(links))
        role = str(cluster.get("device_role") or "").lower()

        if link_count >= 4 or "core" in role or "spine" in role:
            impact_scope = "topology_wide"
        elif link_count >= 2:
            impact_scope = "adjacent_devices"
        else:
            impact_scope = "device_scope"

        cluster["adjacent_devices"] = adjacent_devices[:6]
        cluster["link_count"] = link_count
        cluster["impact_scope"] = impact_scope
        enriched.append(cluster)
    return enriched


def _root_cause_score(cluster: Dict[str, Any]) -> tuple[float, str]:
    severity_weight = {
        "critical": 5.0,
        "high": 4.0,
        "major": 3.0,
        "warning": 2.0,
        "medium": 2.0,
        "low": 1.0,
        "info": 1.0,
    }
    impact_weight = {
        "topology_wide": 2.5,
        "adjacent_devices": 1.6,
        "site_scope": 1.2,
        "device_scope": 0.8,
    }

    source_categories = cluster.get("source_categories") or []
    cross_source_bonus = 1.8 if len(source_categories) > 1 else 0.6
    score = (
        severity_weight.get(str(cluster.get("highest_severity") or "warning").lower(), 2.0)
        + min(float(cluster.get("event_count") or 0) * 0.35, 3.0)
        + min(float(cluster.get("case_count") or 0) * 0.6, 2.4)
        + min(float(cluster.get("ticket_count") or 0) * 0.25, 1.0)
        + impact_weight.get(str(cluster.get("impact_scope") or "device_scope"), 0.8)
        + cross_source_bonus
    )
    reason = (
        f"severity={cluster.get('highest_severity')}, "
        f"events={cluster.get('event_count')}, "
        f"cases={cluster.get('case_count')}, "
        f"sources={len(source_categories)}, "
        f"impact={cluster.get('impact_scope')}"
    )
    return round(score, 2), reason


def _aggregate_root_cause_candidates(clusters: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for cluster in clusters:
        key = "|".join(
            [
                str(cluster.get("site_name") or cluster.get("site_id") or "unknown-site"),
                str(cluster.get("signal_family") or "general"),
                str(cluster.get("root_cause_candidate") or "unknown"),
            ]
        )
        item = merged.setdefault(
            key,
            {
                "candidate_key": key,
                "title": cluster.get("title") or cluster.get("root_cause_candidate") or "根因候选",
                "root_cause_candidate": cluster.get("root_cause_candidate") or "待进一步研判的设备异常",
                "site_name": cluster.get("site_name"),
                "signal_family": cluster.get("signal_family"),
                "merged_cluster_count": 0,
                "event_count": 0,
                "case_count": 0,
                "ticket_count": 0,
                "source_categories": set(),
                "adjacent_devices": set(),
                "representative_device": cluster.get("device_name") or cluster.get("host"),
                "impact_scope": cluster.get("impact_scope"),
                "_score": 0.0,
                "_ranking_reasons": [],
            },
        )
        score, reason = _root_cause_score(cluster)
        item["merged_cluster_count"] += 1
        item["event_count"] += int(cluster.get("event_count") or 0)
        item["case_count"] += int(cluster.get("case_count") or 0)
        item["ticket_count"] += int(cluster.get("ticket_count") or 0)
        item["source_categories"].update(cluster.get("source_categories") or [])
        item["adjacent_devices"].update(cluster.get("adjacent_devices") or [])
        if score > item["_score"]:
            item["_score"] = score
            item["title"] = cluster.get("title") or item["title"]
            item["representative_device"] = cluster.get("device_name") or cluster.get("host") or item["representative_device"]
            item["impact_scope"] = cluster.get("impact_scope") or item["impact_scope"]
        item["_ranking_reasons"].append(reason)

    ranked = []
    for item in merged.values():
        cross_source_bonus = 0.8 if len(item["source_categories"]) > 1 else 0.0
        merged_bonus = min(item["merged_cluster_count"] * 0.45, 2.0)
        total_score = round(float(item["_score"]) + merged_bonus + cross_source_bonus, 2)
        ranked.append(
            {
                "candidate_key": item["candidate_key"],
                "title": item["title"],
                "root_cause_candidate": item["root_cause_candidate"],
                "site_name": item["site_name"],
                "signal_family": item["signal_family"],
                "score": total_score,
                "ranking_reason": " | ".join(item["_ranking_reasons"][:2]),
                "merged_cluster_count": item["merged_cluster_count"],
                "event_count": item["event_count"],
                "case_count": item["case_count"],
                "ticket_count": item["ticket_count"],
                "source_categories": sorted(item["source_categories"]),
                "adjacent_devices": sorted(item["adjacent_devices"])[:8],
                "representative_device": item["representative_device"],
                "impact_scope": item["impact_scope"],
                "recommended_actions": remediation_recommendation_service.build_actions(
                    root_cause=item["root_cause_candidate"],
                    signal_family=item["signal_family"],
                    impact_scope=item["impact_scope"],
                    priority="P1" if total_score >= 8.5 else "P2" if total_score >= 6.5 else "P3",
                    cross_source=len(item["source_categories"]) > 1,
                )[:4],
            }
        )

    return sorted(
        ranked,
        key=lambda value: (value["score"], value["event_count"], value["case_count"]),
        reverse=True,
    )


def _normalize_severity(severity: Optional[str], severity_level: Optional[int]) -> tuple[str, int]:
    if severity_level is None:
        mapped = {
            "critical": 5,
            "high": 4,
            "warning": 2,
            "warn": 2,
            "medium": 2,
            "info": 1,
            "low": 1,
        }
        severity_level = mapped.get((severity or "").lower(), 2)

    if not severity:
        level_to_name = {
            5: "critical",
            4: "high",
            3: "major",
            2: "warning",
            1: "info",
            0: "unknown",
        }
        severity = level_to_name.get(severity_level, "warning")

    return severity, severity_level


def _build_dedup_key(payload: EventIngestRequest) -> str:
    if payload.external_event_id:
        raw_key = f"{payload.source}|{payload.external_event_id}"
    elif payload.fingerprint:
        raw_key = f"{payload.source}|{payload.fingerprint}"
    else:
        bucket = datetime.utcnow().strftime("%Y%m%d%H%M")
        raw_key = f"{payload.source}|{payload.host}|{payload.name}|{bucket}"
    return hashlib.md5(raw_key.encode()).hexdigest()


def _validate_source_centric_ingest(payload: EventIngestRequest) -> tuple[str, str]:
    normalized_source = str(payload.source or "").strip().upper()
    normalized_event_type = str(payload.event_type or "").strip().lower()
    allowed = {
        "ELK": {"log_signal"},
        "ZABBIX": {"zabbix_alert"},
    }
    allowed_event_types = allowed.get(normalized_source)
    if not allowed_event_types:
        raise HTTPException(status_code=400, detail="event source must be ELK or ZABBIX")
    if normalized_event_type not in allowed_event_types:
        raise HTTPException(
            status_code=400,
            detail=f"event_type must be one of {sorted(allowed_event_types)} for source {normalized_source}",
        )
    return normalized_source, normalized_event_type


def _upsert_event(db: Session, payload: EventIngestRequest) -> SourceEvent:
    normalized_source, normalized_event_type = _validate_source_centric_ingest(payload)
    dedup_key = _build_dedup_key(payload)
    severity, severity_level = _normalize_severity(payload.severity, payload.severity_level)
    event_payload = {
        "event_type": normalized_event_type,
        "source_category": payload.raw_payload.get(
            "source_category",
            "log_signal" if normalized_source == "ELK" else "zabbix_alert",
        ),
        "signal_key": payload.raw_payload.get("signal_key"),
        "fingerprint": payload.fingerprint,
        "tags": payload.tags,
        "raw": payload.raw_payload or {},
    }

    source_event = upsert_source_event(
        db,
        dedup_key=f"event:{dedup_key}",
        source_type=normalized_event_type,
        source_system=normalized_source,
        external_event_id=payload.external_event_id,
        site_id=payload.site_id,
        netbox_device_id=payload.netbox_device_id,
        device_ip=payload.host,
        host=payload.host,
        title=payload.name,
        severity=severity,
        occurred_at=payload.occurred_at or datetime.now(),
        collected_at=datetime.now(),
        raw_payload=payload.raw_payload or {},
        normalized_payload={
            "severity": severity,
            "severity_level": severity_level,
            "source_category": event_payload.get("source_category"),
            "event_type": normalized_event_type,
            "signal_key": event_payload.get("signal_key"),
            "fingerprint": payload.fingerprint,
            "tags": payload.tags,
            "event_decision": {},
            "case": {},
            "ticket": {},
        },
        status=SourceEventStatus.NEW,
        legacy_event_id=None,
    )
    attach_event_projection(
        source_event,
        legacy_source=normalized_source,
        legacy_dedup_key=dedup_key,
        host=payload.host,
        severity=severity,
        severity_level=severity_level,
        status="open",
        acknowledged=False,
        occurred_at=payload.occurred_at or datetime.now(),
        last_seen_at=datetime.now(),
        payload={**event_payload, "source_event_id": int(source_event.id) if source_event.id is not None else None},
    )
    return source_event


def _pick_first(*values: Any) -> Optional[Any]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _parse_optional_datetime(raw: Any) -> Optional[datetime]:
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        if raw > 10_000_000_000:
            return datetime.fromtimestamp(raw / 1000)
        return datetime.fromtimestamp(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if text.isdigit():
            return _parse_optional_datetime(int(text))
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def _dispatch_readonly_for_binding(
    *,
    source_event: Optional[SourceEvent],
    reviewer: str,
    db: Session,
) -> Dict[str, Any]:
    event = build_event_shadow(source_event) if source_event is not None else None
    if event is None:
        return {
            "success": False,
            "task_id": None,
            "case_id": None,
            "case_code": None,
            "message": "Event not found",
        }

    case_info = await _resolve_case_for_binding(
        db,
        source_event=source_event,
        force_create=True,
    )
    if not case_info.get("case_id"):
        return {
            "success": False,
            "task_id": None,
            "case_id": None,
            "case_code": None,
            "message": "Failed to resolve case for event",
        }

    playbook_draft = playbook_draft_service.generate_for_event(event)
    playbook_payload = {
        "check": playbook_draft.get("check", {}),
        "generated_at": datetime.now().isoformat(),
    }
    dispatch_payload = {
        "mode": "case_pipeline",
        "reviewer": reviewer,
        "read_only": True,
        "case_id": case_info.get("case_id"),
        "case_code": case_info.get("case_code"),
        "dispatched_at": datetime.now().isoformat(),
    }

    _apply_binding_projection_updates(
        db,
        source_event=source_event,
        playbook_draft=playbook_payload,
        dispatch_info=dispatch_payload,
        acknowledged=True,
        source_status=SourceEventStatus.CASE_CREATED,
    )
    db.commit()

    await case_orchestrator.run_case_pipeline(
        db,
        case_id=case_info["case_id"],
        log_query=event.host or event.name,
        time_range="-30m,now",
        log_limit=300,
    )
    if source_event is not None:
        db.refresh(source_event)
    return {
        "success": True,
        "task_id": None,
        "case_id": case_info.get("case_id"),
        "case_code": case_info.get("case_code"),
        "message": "Read-only diagnosis rerouted to case pipeline",
        "playbook_check": playbook_draft.get("check", {}),
    }


@router.get("/mode", response_model=MessageResponse)
async def get_mode():
    mode = "observe_only" if settings.automation_observe_only else "normal"
    return {"message": mode}


@router.post("/ingest", response_model=EventIngestResponse)
async def ingest_event(payload: EventIngestRequest, db: Session = Depends(get_db)):
    source_event = _upsert_event(db, payload)
    db.commit()
    db.refresh(source_event)
    case_info = await _resolve_case_for_binding(
        db,
        source_event=source_event,
    )
    return {
        "accepted": True,
        "observe_only": settings.automation_observe_only,
        "event": _serialize_source_event(source_event),
        "case_id": case_info.get("case_id"),
        "case_code": case_info.get("case_code"),
    }


def _matches_event_status(view: Dict[str, Any], status: Optional[str]) -> bool:
    if not status:
        return True
    return str(view.get("status") or "").lower() == str(status).lower()


def _load_event_views_from_source_events(
    db: Session,
    *,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    site_id: Optional[int] = None,
    netbox_device_id: Optional[int] = None,
) -> list[Dict[str, Any]]:
    query = db.query(SourceEvent)
    if severity:
        query = query.filter(SourceEvent.severity == severity)
    if source:
        query = query.filter(SourceEvent.source_system == source)
    if site_id is not None:
        query = query.filter(SourceEvent.site_id == site_id)
    if netbox_device_id is not None:
        query = query.filter(SourceEvent.netbox_device_id == netbox_device_id)
    items = query.order_by(SourceEvent.occurred_at.desc()).all()
    return [_serialize_source_event(item) for item in items]

def _find_source_event_by_any_event_id(db: Session, event_id: int) -> Optional[SourceEvent]:
    item = db.query(SourceEvent).filter(SourceEvent.id == event_id).first()
    if item is not None:
        return item
    return db.query(SourceEvent).filter(SourceEvent.legacy_event_id == event_id).first()


def _find_local_ticket_for_binding(
    db: Session,
    *,
    source_event: Optional[SourceEvent],
    ticket_code: Optional[str] = None,
) -> Optional[LocalTicket]:
    if ticket_code:
        ticket = db.query(LocalTicket).filter(LocalTicket.ticket_code == str(ticket_code)).first()
        if ticket is not None:
            return ticket

    if source_event is not None:
        ticket = (
            db.query(LocalTicket)
            .filter(LocalTicket.source_event_id == int(source_event.id))
            .order_by(LocalTicket.created_at.desc())
            .first()
        )
        if ticket is not None:
            return ticket

        candidates = db.query(LocalTicket).order_by(LocalTicket.created_at.desc()).limit(500).all()
        for item in candidates:
            if ((item.ticket_metadata or {}).get("source_event_id") == int(source_event.id)):
                return item
    return None


def _apply_binding_projection_updates(
    db: Session,
    *,
    source_event: Optional[SourceEvent],
    event_decision: Any = _UNSET,
    case_info: Any = _UNSET,
    ticket_info: Any = _UNSET,
    playbook_draft: Any = _UNSET,
    dispatch_info: Any = _UNSET,
    acknowledged: Optional[bool] = None,
    source_status: Optional[SourceEventStatus] = None,
    resolved_at: Any = _UNSET,
) -> None:
    if source_event is not None:
        _update_source_event_projection(
            source_event,
            event_decision=event_decision,
            case_info=case_info,
            ticket_info=ticket_info,
            playbook_draft=playbook_draft,
            dispatch_info=dispatch_info,
            acknowledged=acknowledged,
            status=source_status,
            resolved_at=resolved_at,
        )


def _update_source_event_projection(
    source_event: SourceEvent,
    *,
    event_decision: Any = _UNSET,
    case_info: Any = _UNSET,
    ticket_info: Any = _UNSET,
    playbook_draft: Any = _UNSET,
    dispatch_info: Any = _UNSET,
    acknowledged: Optional[bool] = None,
    status: Optional[SourceEventStatus] = None,
    resolved_at: Any = _UNSET,
) -> None:
    payload = dict(source_event.normalized_payload or {})
    if event_decision is not _UNSET:
        payload["event_decision"] = event_decision or {}
    if case_info is not _UNSET:
        payload["case"] = case_info or {}
    if ticket_info is not _UNSET:
        payload["ticket"] = ticket_info or {}
    if playbook_draft is not _UNSET:
        payload["playbook_draft"] = playbook_draft or {}
    if dispatch_info is not _UNSET:
        payload["dispatch"] = dispatch_info or {}
    if acknowledged is not None:
        payload["legacy_acknowledged"] = bool(acknowledged)
    if resolved_at is not _UNSET:
        payload["legacy_resolved_at"] = resolved_at.isoformat() if resolved_at else None
    payload["legacy_last_seen_at"] = datetime.now().isoformat()
    source_event.normalized_payload = payload
    source_event.collected_at = datetime.now()
    if status is not None:
        source_event.status = status


async def _resolve_case_for_source_event(
    db: Session,
    source_event: SourceEvent,
    *,
    force_create: bool = False,
) -> Dict[str, Any]:
    payload = dict(source_event.normalized_payload or {})
    existing_case = payload.get("case") or {}
    if existing_case.get("case_id") and existing_case.get("case_code"):
        return existing_case

    if not force_create:
        decision = event_decision_service.evaluate_source_event(source_event)
        if decision.get("disposition") != "case_required":
            return {
                "case_id": None,
                "case_code": None,
                "created_at": None,
            }

    case = await case_orchestrator.intake_case(
        db,
        title=source_event.title,
        source_type=payload.get("event_type") or source_event.source_type or "event",
        source_system=source_event.source_system,
        dedup_key=source_event.dedup_key,
        severity=source_event.severity,
        site_id=source_event.site_id,
        netbox_device_id=source_event.netbox_device_id,
        device_ip=source_event.device_ip,
        host=source_event.host,
        summary=f"Event intake from {source_event.source_system}, severity={source_event.severity}",
        occurred_at=source_event.occurred_at,
        raw_payload=source_event.raw_payload or payload.get("raw") or payload,
        normalized_payload=payload,
        case_metadata={
            "linked_source_event_id": int(source_event.id),
            "linked_event_id": payload.get("legacy_event_id"),
            "recommended_skill_code": payload.get("recommended_skill_code"),
        },
    )
    case_info = {
        "case_id": case.id,
        "case_code": case.case_code,
        "created_at": datetime.now().isoformat(),
    }
    _update_source_event_projection(
        source_event,
        case_info=case_info,
        event_decision={
            "disposition": "case_required",
            "reason": "case_created",
            "confidence": 0.99,
            "updated_at": datetime.now().isoformat(),
        },
        acknowledged=True,
        status=SourceEventStatus.CASE_CREATED,
    )
    db.commit()
    return case_info


async def _resolve_case_for_binding(
    db: Session,
    *,
    source_event: Optional[SourceEvent],
    force_create: bool = False,
) -> Dict[str, Any]:
    if source_event is not None:
        return await _resolve_case_for_source_event(db, source_event, force_create=force_create)
    return {
        "case_id": None,
        "case_code": None,
        "created_at": None,
    }


@router.get("", response_model=EventListResponse)
async def list_events(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    source_category: Optional[str] = None,
    disposition: Optional[str] = None,
    site_id: Optional[int] = None,
    netbox_device_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    records = _load_event_views_from_source_events(
        db,
        severity=severity,
        source=source,
        site_id=site_id,
        netbox_device_id=netbox_device_id,
    )
    if status:
        records = [item for item in records if _matches_event_status(item, status)]
    if event_type:
        records = [item for item in records if (item.get("payload") or {}).get("event_type") == event_type]
    if source_category:
        records = [item for item in records if item.get("source_category") == source_category]
    if disposition:
        records = [item for item in records if item.get("disposition") == disposition]

    total = len(records)
    records = records[skip : skip + limit]
    returned = len(records)

    return {
        "page": PageMeta(
            total=total,
            skip=skip,
            limit=limit,
            returned=returned,
            has_more=(skip + returned) < total,
        ),
        "events": records,
    }


@router.get("/clusters", response_model=EventClusterListResponse)
async def list_event_clusters(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    disposition: Optional[str] = None,
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    records = _load_event_views_from_source_events(
        db,
        severity=severity,
        source=source,
    )[:500]
    if status:
        records = [item for item in records if _matches_event_status(item, status)]
    if disposition:
        records = [item for item in records if item.get("disposition") == disposition]

    clusters = _aggregate_clusters(records, db)[:limit]
    return {
        "clusters": await _enrich_clusters_with_topology(clusters),
    }


@router.get("/root-causes", response_model=RootCauseCandidateListResponse)
async def list_root_cause_candidates(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    disposition: Optional[str] = None,
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
):
    records = _load_event_views_from_source_events(
        db,
        severity=severity,
        source=source,
    )[:500]
    if status:
        records = [item for item in records if _matches_event_status(item, status)]
    if disposition:
        records = [item for item in records if item.get("disposition") == disposition]

    clusters = _aggregate_clusters(records, db)[: max(limit * 3, 12)]
    clusters = await _enrich_clusters_with_topology(clusters)
    return {
        "items": _aggregate_root_cause_candidates(clusters)[:limit],
    }


@router.post("/{event_id}/dispatch-readonly", response_model=EventDispatchResponse)
async def dispatch_readonly_diagnosis(
    event_id: int,
    payload: EventDispatchRequest,
    db: Session = Depends(get_db),
):
    source_event = _find_source_event_by_any_event_id(db, event_id)
    if source_event is None:
        return {"success": False, "message": "Event not found", "task_id": None}

    result = await _dispatch_readonly_for_binding(
        source_event=source_event,
        reviewer=payload.reviewer or "system",
        db=db,
    )
    return {
        "success": bool(result.get("success", False)),
        "message": result.get("message", ""),
        "task_id": result.get("task_id"),
        "case_id": result.get("case_id"),
        "case_code": result.get("case_code"),
        "playbook_check": result.get("playbook_check", {}),
    }


@router.post("/{event_id}/disposition", response_model=MessageResponse)
async def update_event_disposition(
    event_id: int,
    payload: EventDispositionRequest,
    db: Session = Depends(get_db),
):
    source_event = _find_source_event_by_any_event_id(db, event_id)
    if source_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    disposition = (payload.disposition or "").strip().lower()
    if disposition not in {"noise", "ticket_only", "case_required"}:
        raise HTTPException(status_code=400, detail="disposition must be noise|ticket_only|case_required")

    decision_payload = {
        "disposition": disposition,
        "reason": (payload.reason or "").strip() or "manual_override",
        "confidence": 0.99,
        "updated_at": datetime.now().isoformat(),
    }
    resolved_at = datetime.now() if disposition == "noise" else None

    _apply_binding_projection_updates(
        db,
        source_event=source_event,
        event_decision=decision_payload,
        acknowledged=True,
        source_status=SourceEventStatus.CLOSED if disposition == "noise" else SourceEventStatus.CORRELATED,
        resolved_at=resolved_at if disposition == "noise" else _UNSET,
    )

    db.commit()
    if disposition == "noise":
        return {"message": "Event disposition updated"}
    if disposition == "case_required":
        await _resolve_case_for_binding(db, source_event=source_event, force_create=True)
    return {"message": "Event disposition updated"}


@router.post("/{event_id}/playbook-draft-check", response_model=EventPlaybookDraftResponse)
async def generate_event_playbook_draft(
    event_id: int,
    payload: EventPlaybookDraftRequest,
    db: Session = Depends(get_db),
):
    source_event = _find_source_event_by_any_event_id(db, event_id)
    event = build_event_shadow(source_event) if source_event is not None else None
    if event is None:
        return {
            "success": False,
            "message": "Event not found",
            "event_id": event_id,
            "playbook_check": {"passed": False, "errors": ["event_not_found"], "warnings": []},
            "playbook_yaml": "",
        }

    draft = playbook_draft_service.generate_for_event(event)
    playbook_payload = {
        "check": draft.get("check", {}),
        "generated_at": datetime.now().isoformat(),
    }

    _apply_binding_projection_updates(
        db,
        source_event=source_event,
        playbook_draft=playbook_payload,
    )
    db.commit()

    return {
        "success": True,
        "message": "Playbook draft generated",
        "event_id": event_id,
        "playbook_check": draft.get("check", {}),
        "playbook_yaml": draft.get("playbook_yaml", "") if payload.include_playbook else "",
    }


@router.post("/{event_id}/ticket", response_model=EventTicketResponse)
async def create_event_ticket(
    event_id: int,
    payload: EventTicketCreateRequest,
    db: Session = Depends(get_db),
):
    source_event = _find_source_event_by_any_event_id(db, event_id)
    event = build_event_shadow(source_event) if source_event is not None else None
    if event is None:
        return {"success": False, "message": "Event not found", "ticket_id": None, "provider": None}

    ticket_payload = {
        "title": payload.title or f"[{event.severity}] {event.name}",
        "description": payload.description or f"source={event.source}, host={event.host}, event_id={event.id}",
        "priority": payload.priority,
        "requester": payload.requester,
        "metadata": {
            "event_id": event.id,
            "source_event_id": int(source_event.id) if source_event is not None else None,
            "external_event_id": event.external_event_id,
            "site_id": event.site_id,
            "netbox_device_id": event.netbox_device_id,
            "severity": event.severity,
            "status": event.status,
        },
    }

    if (settings.ticket_mode or "local").lower() != "external" or not settings.ticket_system_base_url:
        ticket_code = f"LOCAL-{int(datetime.now().timestamp() * 1000)}"
        local_ticket = LocalTicket(
            ticket_code=ticket_code,
            provider="local",
            event_id=None,
            source_event_id=int(source_event.id) if source_event is not None else None,
            title=ticket_payload["title"],
            description=ticket_payload["description"],
            priority=ticket_payload.get("priority") or "P3",
            requester=ticket_payload.get("requester") or "netops-automation",
            status="open",
            ticket_metadata=ticket_payload.get("metadata") or {},
        )
        db.add(local_ticket)
        db.flush()
        result = {
            "success": True,
            "ticket_id": ticket_code,
            "status": local_ticket.status,
            "provider": "local",
            "local_ticket_id": local_ticket.id,
        }
    else:
        result = await ticket_adapter.create_ticket(ticket_payload)

    ticket_info = {
        "ticket_id": result.get("ticket_id"),
        "provider": result.get("provider"),
        "status": result.get("status"),
        "local_ticket_id": result.get("local_ticket_id"),
        "created_at": datetime.now().isoformat(),
    }
    decision_payload = {
        "disposition": "ticket_only",
        "reason": "ticket_created",
        "confidence": 0.99,
        "updated_at": datetime.now().isoformat(),
    }
    _apply_binding_projection_updates(
        db,
        source_event=source_event,
        ticket_info=ticket_info,
        event_decision=decision_payload,
        acknowledged=True if source_event is not None else None,
        source_status=SourceEventStatus.CORRELATED,
    )
    db.commit()

    return {
        "success": bool(result.get("success", False)),
        "message": "Ticket created" if result.get("success") else "Ticket creation failed",
        "ticket_id": result.get("ticket_id"),
        "provider": result.get("provider"),
    }


@router.get("/{event_id}/relations", response_model=EventRelationsResponse)
async def get_event_relations(event_id: int, db: Session = Depends(get_db)):
    source_event = _find_source_event_by_any_event_id(db, event_id)
    event = build_event_shadow(source_event) if source_event is not None else None
    if event is None:
        return {"event_id": event_id, "ticket": {}, "linked_case": None, "linked_tasks": []}

    ticket_info = (event.payload or {}).get("ticket") or {}
    ticket_code = ticket_info.get("ticket_id")
    try:
        local_ticket = _find_local_ticket_for_binding(
            db,
            source_event=source_event,
            ticket_code=ticket_code,
        )
        if local_ticket:
            ticket_info = {
                "ticket_id": local_ticket.ticket_code,
                "provider": local_ticket.provider,
                "status": local_ticket.status,
                "priority": local_ticket.priority,
                "requester": local_ticket.requester,
                "event_id": local_ticket.event_id,
                "source_event_id": local_ticket.source_event_id or (local_ticket.ticket_metadata or {}).get("source_event_id"),
                "created_at": local_ticket.created_at.isoformat() if local_ticket.created_at else None,
                "updated_at": local_ticket.updated_at.isoformat() if local_ticket.updated_at else None,
            }
    except Exception:
        ticket_info = ticket_info

    case_info = (event.payload or {}).get("case") or {}
    linked_case = None
    linked = []
    if case_info.get("case_id") and case_info.get("case_code"):
        linked_case = {
            "case_id": case_info.get("case_id"),
            "case_code": case_info.get("case_code"),
            "created_at": case_info.get("created_at"),
        }
        plans = (
            db.query(RemediationPlan)
            .filter(RemediationPlan.case_id == case_info.get("case_id"))
            .order_by(RemediationPlan.created_at.desc())
            .all()
        )
        execution_rows = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.case_id == case_info.get("case_id"))
            .order_by(ExecutionRun.started_at.desc())
            .all()
        )
        execution_by_plan = {}
        for item in execution_rows:
            execution_by_plan.setdefault(item.remediation_plan_id, item)

        for plan in plans:
            latest_execution = execution_by_plan.get(plan.id)
            linked.append(
                {
                    "task_id": int(plan.id),
                    "task_code": plan.plan_code,
                    "status": (
                        latest_execution.status.value
                        if latest_execution and hasattr(latest_execution.status, "value")
                        else str(latest_execution.status)
                        if latest_execution
                        else plan.status.value if hasattr(plan.status, "value") else str(plan.status)
                    ),
                    "created_at": latest_execution.started_at if latest_execution else plan.created_at,
                    "source_model": "remediation_plan",
                    "case_id": plan.case_id,
                }
            )

    return {
        "event_id": int(source_event.legacy_event_id or source_event.id),
        "ticket": ticket_info,
        "linked_case": linked_case,
        "linked_tasks": linked,
    }
