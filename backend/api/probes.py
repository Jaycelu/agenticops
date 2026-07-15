from __future__ import annotations

import base64
from typing import Any

import paramiko
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from audit.service import security_audit_service
from auth.dependencies import require_permissions
from auth.rbac import Permission
from auth.schemas import Principal
from database import get_db
from models.probe import DeviceHostKey
from probes.catalog import probe_catalog
from probes.gateway import ProbeRejected, probe_gateway
from probes.schemas import ProbeRequest
from probes.ssh_transport import sha256_fingerprint


router = APIRouter(prefix="/api/probes", tags=["probes"])


class HostKeyRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    netbox_device_id: int = Field(gt=0)
    hostname: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    algorithm: str = Field(min_length=1, max_length=80)
    public_key_base64: str = Field(min_length=16, max_length=16384)


@router.get("/catalog")
def list_probe_catalog(
    principal: Principal = Depends(require_permissions(Permission.PROBES_RUN.value)),
) -> dict[str, Any]:
    del principal
    return {"version": probe_catalog.version, "items": probe_catalog.list_public()}


@router.post("/run")
def run_probe(
    request: ProbeRequest,
    principal: Principal = Depends(require_permissions(Permission.PROBES_RUN.value)),
    db: Session = Depends(get_db),
):
    try:
        return probe_gateway.run(db, request, principal)
    except ProbeRejected as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/host-keys")
def list_host_keys(
    principal: Principal = Depends(require_permissions(Permission.CREDENTIALS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    del principal
    rows = db.query(DeviceHostKey).filter(DeviceHostKey.active.is_(True)).order_by(DeviceHostKey.netbox_device_id).all()
    return {
        "items": [
            {
                "id": int(row.id),
                "netbox_device_id": row.netbox_device_id,
                "hostname": row.hostname,
                "port": row.port,
                "algorithm": row.algorithm,
                "fingerprint_sha256": row.fingerprint_sha256,
                "verified_at": row.verified_at,
            }
            for row in rows
        ]
    }


@router.put("/host-keys")
def register_host_key(
    payload: HostKeyRegistration,
    principal: Principal = Depends(require_permissions(Permission.CREDENTIALS_MANAGE.value)),
    db: Session = Depends(get_db),
):
    try:
        key_bytes = base64.b64decode(payload.public_key_base64, validate=True)
        key = paramiko.PKey.from_type_string(payload.algorithm, key_bytes)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid SSH public key") from exc
    fingerprint = sha256_fingerprint(key)
    db.query(DeviceHostKey).filter(
        DeviceHostKey.netbox_device_id == payload.netbox_device_id,
        DeviceHostKey.port == payload.port,
        DeviceHostKey.active.is_(True),
    ).update({"active": False}, synchronize_session=False)
    row = DeviceHostKey(
        netbox_device_id=payload.netbox_device_id,
        hostname=payload.hostname.strip(),
        port=payload.port,
        algorithm=payload.algorithm,
        public_key_base64=payload.public_key_base64,
        fingerprint_sha256=fingerprint,
        active=True,
        verified_by_user_id=principal.user_id,
    )
    db.add(row)
    db.flush()
    security_audit_service.append(
        db,
        event_type="probe.host_key.registered",
        outcome="success",
        actor_user_id=principal.user_id,
        actor_session_id=principal.session_id,
        target_type="device_host_key",
        target_id=str(row.id),
        details={
            "netbox_device_id": payload.netbox_device_id,
            "port": payload.port,
            "algorithm": payload.algorithm,
            "fingerprint_sha256": fingerprint,
        },
    )
    db.commit()
    return {"id": int(row.id), "fingerprint_sha256": fingerprint}
