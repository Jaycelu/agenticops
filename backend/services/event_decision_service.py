from __future__ import annotations

import re
from typing import Any, Dict, Optional

from models.agenticops import SourceEvent


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
        if normalized == "ELK":
            return "log_signal"
        if normalized == "ZABBIX":
            return "zabbix_alert"
        return "unknown"

    def get_source_label(self, source: str, payload: Optional[Dict[str, Any]] = None) -> str:
        source_category = self.get_source_category(source, payload)
        if source_category == "log_signal":
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

        tokens = [token for token in re.split(r"[:._\\-/]+", raw) if token]
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


event_decision_service = EventDecisionService()
