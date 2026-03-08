from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from models.automation import AutomationTask, LogSample, SSHCredentialDeviceBinding
from services.log_sampler import log_sampler
from services.ssh_service import ssh_service


def dispatch_config_precheck_action(db: Session, task_id: int) -> Dict[str, Any]:
    task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()
    if task is None:
        raise LookupError("Task not found")

    if task.status in {"waiting_confirm", "waiting_approval", "aborted", "cancelled"} or bool(task.need_human_confirm):
        raise ValueError("task is not eligible for dispatch pre-check, complete manual confirmation/approval first")

    context = (task.decision_result or {}).get("context", {})
    device_id = context.get("netbox_device_id")
    if not device_id:
        raise ValueError("task has no netbox device")

    binding = db.query(SSHCredentialDeviceBinding).filter(
        SSHCredentialDeviceBinding.netbox_device_id == device_id
    ).order_by(SSHCredentialDeviceBinding.updated_at.desc()).first()
    if binding is None:
        raise ValueError("no ssh credential binding found for this device")

    try:
        dry_run_result = ssh_service.execute_commands(
            db=db,
            credential_id=binding.credential_id,
            netbox_device_id=device_id,
            commands=["display current-configuration", "show running-config"],
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"dispatch pre-check failed: {exc}") from exc

    trail = list(task.audit_trail or [])
    trail.append(
        {
            "stage": "Inspection",
            "title": "人工触发一键下发前置检查",
            "payload": {
                "operator_action": "dispatch_config",
                "dry_run": dry_run_result,
            },
        }
    )
    task.audit_trail = trail
    db.commit()

    return {
        "success": True,
        "message": "已执行下发前置检查，后续可按变更流程执行正式配置下发",
        "data": dry_run_result,
    }


async def trigger_diagnosis_action(db: Session, sample_id: int) -> Dict[str, Any]:
    sample = db.query(LogSample).filter(LogSample.id == sample_id).first()
    if sample is None:
        raise LookupError("Sample not found")

    try:
        result = await log_sampler.create_case_for_sample(sample_id, rerun_pipeline=True)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(str(exc)) from exc

    return {
        "success": True,
        "message": f"Case pipeline triggered for sample {sample_id}",
        "data": result,
    }
