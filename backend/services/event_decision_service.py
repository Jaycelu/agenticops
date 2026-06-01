from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import func, or_

from config.pipeline_thresholds import (
    CLUSTER_COUNT_NOISE_TO_TICKET,
    CLUSTER_COUNT_TO_CASE,
    CROSS_SOURCE_PEER_BOOST_MIN,
    CROSS_SOURCE_WINDOW_MINUTES,
)
from models.agenticops import CaseRecord, CaseStatus, SourceEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class EventDecisionService:
    """Builds a consistent event view for the Event Center."""

    def _evaluate(
        self,
        *,
        source: str,
        payload: Dict[str, Any],
        severity: str,
        severity_level: int,
        status: str,
        site_id: Optional[int],
        netbox_device_id: Optional[int],
        host: Optional[str],
    ) -> Dict[str, Any]:
        manual = dict(payload.get("event_decision") or {})
        source_category = self.get_source_category(source, payload)
        signal_key = payload.get("signal_key")
        case_info = self.get_case_info(payload)
        ticket_info = self.get_ticket_info(payload)

        disposition = str(manual.get("disposition") or "").strip().lower()
        reason = str(manual.get("reason") or "").strip()
        confidence = manual.get("confidence")

        signal_summary = (
            payload.get("signal_summary")
            or (payload.get("raw") or {}).get("signal_summary")
            or {}
        )
        risk_level = str(
            signal_summary.get("risk_level")
            or payload.get("risk_level")
            or severity
            or "warning"
        ).lower()
        should_create_case = bool(
            signal_summary.get("should_create_case")
            or signal_summary.get("trigger_mode") in {"case", "auto_case"}
            or payload.get("case_candidate")
        )

        if not disposition:
            if case_info.get("case_id"):
                disposition = "case_required"
                reason = "linked_case_exists"
                confidence = 0.96
            elif ticket_info.get("ticket_id"):
                disposition = "ticket_only"
                reason = "linked_ticket_exists"
                confidence = 0.92
            elif status == "resolved":
                disposition = "noise"
                reason = "resolved_event"
                confidence = 0.88
            elif source_category == "zabbix_alert":
                if severity_level >= 4:
                    disposition = "case_required"
                    reason = "high_risk_zabbix_alert"
                    confidence = 0.84
                elif severity_level >= 2:
                    disposition = "ticket_only"
                    reason = "zabbix_alert_requires_human_followup"
                    confidence = 0.76
                else:
                    disposition = "noise"
                    reason = "low_risk_zabbix_alert"
                    confidence = 0.68
            elif source_category == "log_signal":
                if should_create_case or risk_level in {"critical", "high"} or severity_level >= 4:
                    disposition = "case_required"
                    reason = "log_signal_requires_case"
                    confidence = 0.82
                elif risk_level in {"warning", "medium"} or severity_level >= 2:
                    disposition = "ticket_only"
                    reason = "log_signal_requires_followup"
                    confidence = 0.72
                else:
                    disposition = "noise"
                    reason = "low_risk_log_signal"
                    confidence = 0.62
            else:
                if severity_level >= 4:
                    disposition = "case_required"
                    reason = "unsupported_source_requires_case"
                    confidence = 0.7
                elif severity_level >= 2:
                    disposition = "ticket_only"
                    reason = "unsupported_source_requires_followup"
                    confidence = 0.6
                else:
                    disposition = "noise"
                    reason = "unsupported_source_low_risk"
                    confidence = 0.5

        return {
            "disposition": disposition or "ticket_only",
            "reason": reason or "auto_evaluated",
            "confidence": float(confidence or 0.5),
            "signal_key": signal_key,
            "signal_family": self._signal_family(signal_key),
            "cluster_key": self.build_cluster_key(
                source_category=source_category,
                site_id=site_id,
                netbox_device_id=netbox_device_id,
                host=host,
                signal_key=signal_key,
            ),
            "correlation_key": self.build_correlation_key(
                site_id=site_id,
                netbox_device_id=netbox_device_id,
                host=host,
                signal_key=signal_key,
            ),
        }

    def get_source_category(self, source: str, payload: Optional[Dict[str, Any]] = None) -> str:
        payload = payload or {}
        explicit = str(payload.get("source_category") or "").strip()
        if explicit:
            return explicit

        normalized = (source or "").upper()
        if normalized in {"ELK", "ELK_SAMPLER"}:
            return "log_signal"
        if normalized == "ZABBIX":
            return "zabbix_alert"
        return "unknown"

    def get_source_label(self, source: str, payload: Optional[Dict[str, Any]] = None) -> str:
        source_category = self.get_source_category(source, payload)
        if source_category == "log_signal":
            if (source or "").upper() == "ELK_SAMPLER":
                return "ELK 采样日志信号"
            return "ELK 日志信号"
        if source_category == "zabbix_alert":
            return "Zabbix 告警"
        return source or "unknown"

    def get_case_info(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        case_info = payload.get("case") or {}
        return {
            "case_id": case_info.get("case_id"),
            "case_code": case_info.get("case_code"),
            "created_at": case_info.get("created_at"),
        }

    def get_ticket_info(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        ticket_info = payload.get("ticket") or {}
        return {
            "ticket_id": ticket_info.get("ticket_id"),
            "provider": ticket_info.get("provider"),
            "status": ticket_info.get("status"),
            "created_at": ticket_info.get("created_at"),
        }

    def build_cluster_key(
        self,
        *,
        source_category: str,
        site_id: Optional[int],
        netbox_device_id: Optional[int],
        host: Optional[str],
        signal_key: Optional[str],
    ) -> str:
        anchor = signal_key or host or "unmapped"
        site_scope = f"site:{site_id}" if site_id else "site:unknown"
        device_scope = f"device:{netbox_device_id}" if netbox_device_id else f"host:{host or 'unknown'}"
        return f"{source_category}:{site_scope}:{device_scope}:{anchor}"

    def _signal_family(self, signal_key: Optional[str]) -> str:
        raw = str(signal_key or "").strip().lower()
        if not raw:
            return "general"

        tokens = [token for token in re.split(r"[:._\\/-]+", raw) if token]
        if not tokens:
            return "general"

        ignored = {"log", "signal", "device", "event", "alert", "sample", "sampler", "zabbix", "elk"}
        useful = [token for token in tokens if token not in ignored]
        return useful[0] if useful else tokens[0]

    def build_correlation_key(
        self,
        *,
        site_id: Optional[int],
        netbox_device_id: Optional[int],
        host: Optional[str],
        signal_key: Optional[str],
    ) -> str:
        site_scope = f"site:{site_id}" if site_id else "site:unknown"
        entity_scope = f"device:{netbox_device_id}" if netbox_device_id else f"host:{host or 'unknown'}"
        family = self._signal_family(signal_key)
        return f"{site_scope}:{entity_scope}:family:{family}"

    def evaluate_record(self, record: Any) -> Dict[str, Any]:
        payload = dict(record.payload or {})
        return self._evaluate(
            source=record.source,
            payload=payload,
            severity=record.severity,
            severity_level=int(record.severity_level or 0),
            status=str(record.status or "open"),
            site_id=record.site_id,
            netbox_device_id=record.netbox_device_id,
            host=record.host,
        )

    def evaluate_source_event(self, record: SourceEvent) -> Dict[str, Any]:
        payload = dict(record.normalized_payload or {})
        payload.setdefault("raw", record.raw_payload or {})
        severity_level = int(payload.get("severity_level") or 0)
        record_status = record.status.value if hasattr(record.status, "value") else str(record.status or "open")
        status = str(payload.get("legacy_status") or record_status)
        return self._evaluate(
            source=record.source_system,
            payload=payload,
            severity=record.severity,
            severity_level=severity_level,
            status=status,
            site_id=record.site_id,
            netbox_device_id=record.netbox_device_id,
            host=record.host,
        )

    def _cluster_context_stats(self, db: "Session", record: SourceEvent, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Rolling window stats for harness-style routing (PostgreSQL)."""
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        q = db.query(func.count(SourceEvent.id)).filter(SourceEvent.collected_at >= since)
        if record.site_id is not None:
            q = q.filter(SourceEvent.site_id == record.site_id)
        if record.netbox_device_id is not None:
            q = q.filter(SourceEvent.netbox_device_id == record.netbox_device_id)
        elif record.host:
            q = q.filter(SourceEvent.host == record.host)
        cluster_window_count = int(q.scalar() or 0)

        open_case = db.query(func.count(CaseRecord.id)).filter(
            CaseRecord.status.not_in([CaseStatus.RESOLVED, CaseStatus.CLOSED]),
        )
        if record.netbox_device_id is not None:
            open_case = open_case.filter(CaseRecord.netbox_device_id == record.netbox_device_id)
        elif record.host:
            open_case = open_case.filter(CaseRecord.host == record.host)
        elif record.site_id is not None:
            open_case = open_case.filter(CaseRecord.site_id == record.site_id)
        open_case_same_anchor = int(open_case.scalar() or 0) > 0

        cross = self._cross_source_peer_stats(db, record)
        return {
            "cluster_window_count": cluster_window_count,
            "open_case_same_anchor": open_case_same_anchor,
            "cluster_key": decision.get("cluster_key"),
            **cross,
        }

    def _opposite_source_systems(self, record: SourceEvent) -> list[str]:
        """Sources that count as cross-domain peers (log vs alert) for correlation."""
        payload = dict(record.normalized_payload or {})
        cat = self.get_source_category(record.source_system, payload)
        if cat == "zabbix_alert":
            return ["ELK", "ELK_SAMPLER"]
        if cat == "log_signal":
            return ["ZABBIX"]
        return []

    def _cross_source_peer_stats(self, db: "Session", record: SourceEvent) -> Dict[str, Any]:
        """Count recent events from the opposite signal family on the same device/host."""
        others = self._opposite_source_systems(record)
        window_minutes = CROSS_SOURCE_WINDOW_MINUTES
        if not others:
            return {
                "cross_source_peer_count": 0,
                "cross_source_window_minutes": window_minutes,
            }
        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        q = (
            db.query(func.count(SourceEvent.id))
            .filter(SourceEvent.collected_at >= since)
            .filter(SourceEvent.id != record.id)
        )
        if record.netbox_device_id is not None:
            q = q.filter(SourceEvent.netbox_device_id == record.netbox_device_id)
        elif record.host:
            q = q.filter(SourceEvent.host == record.host)
        else:
            return {
                "cross_source_peer_count": 0,
                "cross_source_window_minutes": window_minutes,
            }
        q = q.filter(or_(*[SourceEvent.source_system == s for s in others]))
        peer_count = int(q.scalar() or 0)
        return {
            "cross_source_peer_count": peer_count,
            "cross_source_window_minutes": window_minutes,
        }

    def enrich_decision_for_context(self, db: "Session", record: SourceEvent, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Augment disposition with DB-backed cluster and case-anchor signals (measurable harness)."""
        merged = dict(decision)
        try:
            stats = self._cluster_context_stats(db, record, decision)
        except Exception:
            stats = {}
        merged["context_stats"] = stats

        if stats.get("open_case_same_anchor"):
            merged["disposition"] = "case_required"
            merged["reason"] = "open_case_same_anchor"
            merged["confidence"] = max(float(merged.get("confidence") or 0.5), 0.9)
            return merged

        cw = int(stats.get("cluster_window_count") or 0)
        if cw >= CLUSTER_COUNT_NOISE_TO_TICKET and merged.get("disposition") == "noise":
            merged["disposition"] = "ticket_only"
            merged["reason"] = "cluster_frequency_escalation"
            merged["confidence"] = min(0.95, float(merged.get("confidence") or 0.5) + 0.12)

        if cw >= CLUSTER_COUNT_TO_CASE and merged.get("disposition") in {"noise", "ticket_only"}:
            merged["disposition"] = "case_required"
            merged["reason"] = "sustained_cluster_requires_case"
            merged["confidence"] = max(float(merged.get("confidence") or 0.5), 0.88)

        peers = int(stats.get("cross_source_peer_count") or 0)
        sev = int(dict(record.normalized_payload or {}).get("severity_level") or 0)
        if (
            peers >= CROSS_SOURCE_PEER_BOOST_MIN
            and merged.get("disposition") == "ticket_only"
            and 2 <= sev < 4
        ):
            merged["disposition"] = "case_required"
            merged["reason"] = "cross_source_correlation"
            merged["confidence"] = max(float(merged.get("confidence") or 0.5), 0.86)

        return merged


event_decision_service = EventDecisionService()
