from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.automation import LogAnalysisResult, LogSample


def _parse_date(date_str: Optional[str], field_name: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} format, use YYYY-MM-DD") from exc


def list_compat_log_samples(
    db: Session,
    *,
    site_id: Optional[int] = None,
    is_abnormal: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    query = db.query(LogSample)

    if site_id:
        query = query.filter(LogSample.site_id == site_id)
    if is_abnormal is not None:
        query = query.filter(LogSample.is_abnormal == is_abnormal)

    start_datetime = _parse_date(start_date, "start_date")
    if start_datetime:
        query = query.filter(LogSample.sampled_at >= start_datetime)

    end_datetime = _parse_date(end_date, "end_date")
    if end_datetime:
        query = query.filter(LogSample.sampled_at < end_datetime + timedelta(days=1))

    total = query.count()
    samples = query.order_by(LogSample.sampled_at.desc()).offset(skip).limit(limit).all()

    serialized = []
    for sample in samples:
        raw_data = sample.raw_data if isinstance(sample.raw_data, dict) else {}
        signal_summary = raw_data.get("signal_summary")
        serialized.append(
            {
                "id": sample.id,
                "netbox_device_id": sample.netbox_device_id,
                "site_id": sample.site_id,
                "error_count": sample.error_count,
                "crc_error_count": sample.crc_error_count,
                "flap_count": sample.flap_count,
                "neighbor_change_count": sample.neighbor_change_count,
                "sampled_at": sample.sampled_at,
                "time_window_start": sample.time_window_start,
                "time_window_end": sample.time_window_end,
                "is_abnormal": sample.is_abnormal,
                "abnormal_type": signal_summary.get("primary_signal") if signal_summary else None,
                "raw_data": sample.raw_data,
                "created_at": sample.created_at,
                "batch_id": raw_data.get("batch_id"),
                "signal_summary": signal_summary,
                "trigger_reason": raw_data.get("trigger_reason"),
                "case_id": (raw_data.get("case") or {}).get("case_id"),
                "case_code": (raw_data.get("case") or {}).get("case_code"),
                "device_ip": raw_data.get("device_ip"),
            }
        )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "returned": len(serialized),
        "has_more": skip + len(serialized) < total,
        "samples": serialized,
    }


def get_compat_log_sample(db: Session, sample_id: int) -> LogSample:
    sample = db.query(LogSample).filter(LogSample.id == sample_id).first()
    if sample is None:
        raise LookupError("Sample not found")
    return sample


def list_compat_analysis_results(
    db: Session,
    *,
    site_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    query = db.query(LogAnalysisResult)

    if site_id:
        query = query.filter(LogAnalysisResult.site_id == site_id)
    if severity:
        query = query.filter(LogAnalysisResult.severity == severity)
    if status:
        query = query.filter(LogAnalysisResult.status == status)

    start_datetime = _parse_date(start_date, "start_date")
    if start_datetime:
        query = query.filter(LogAnalysisResult.created_at >= start_datetime)

    end_datetime = _parse_date(end_date, "end_date")
    if end_datetime:
        query = query.filter(LogAnalysisResult.created_at < end_datetime + timedelta(days=1))

    total = query.count()
    results = query.order_by(LogAnalysisResult.created_at.desc()).offset(skip).limit(limit).all()

    serialized = []
    for result in results:
        result_dict = {
            "id": result.id,
            "netbox_device_id": result.netbox_device_id,
            "site_id": result.site_id,
            "related_sample_id": result.related_sample_id,
            "analysis_type": result.analysis_type,
            "confidence": result.confidence,
            "summary": result.summary,
            "severity": result.severity,
            "recommendation": result.recommendation,
            "evidence": result.evidence,
            "status": result.status,
            "created_at": result.created_at,
            "updated_at": result.updated_at,
        }

        if result.related_sample_id:
            sample = db.query(LogSample).filter(LogSample.id == result.related_sample_id).first()
            raw_data = sample.raw_data if sample and isinstance(sample.raw_data, dict) else {}
            if raw_data.get("device_ip"):
                result_dict["device_ip"] = raw_data["device_ip"]

        serialized.append(result_dict)

    return {
        "total": total,
        "results": serialized,
    }


def get_compat_analysis_result(db: Session, result_id: int) -> LogAnalysisResult:
    result = db.query(LogAnalysisResult).filter(LogAnalysisResult.id == result_id).first()
    if result is None:
        raise LookupError("Analysis result not found")
    return result
