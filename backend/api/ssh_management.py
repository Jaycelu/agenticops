from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.ssh_management import (
    ConnectivityTestRequest,
    DeviceBindingRequest,
    SSHCredentialCreateRequest,
    SSHCredentialUpdateRequest,
)
from database import get_db
from services.ssh_service import ssh_service

router = APIRouter(prefix="/api/ssh", tags=["ssh-management"])


@router.get("/credentials")
async def list_credentials(db: Session = Depends(get_db)):
    return {"success": True, "data": ssh_service.list_credentials(db)}


@router.post("/credentials")
async def create_credential(payload: SSHCredentialCreateRequest, db: Session = Depends(get_db)):
    try:
        credential = ssh_service.create_credential(db, payload.model_dump())
        return {"success": True, "data": credential}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/credentials/{credential_id}")
async def update_credential(credential_id: int, payload: SSHCredentialUpdateRequest, db: Session = Depends(get_db)):
    try:
        credential = ssh_service.update_credential(db, credential_id, payload.model_dump(exclude_unset=True))
        return {"success": True, "data": credential}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: int, db: Session = Depends(get_db)):
    try:
        ssh_service.delete_credential(db, credential_id)
        return {"success": True, "message": "deleted"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/netbox/devices")
async def query_netbox_devices(
    site: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    name: str | None = Query(default=None),
    role: str | None = Query(default=None),
    vendor: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
):
    try:
        devices = ssh_service.query_netbox_devices(
            site=site,
            tag=tag,
            name=name,
            role=role,
            vendor=vendor,
            device_type=device_type,
        )
        return {"success": True, "data": devices}
    except Exception as exc:  # noqa: BLE001
        if "netbox_not_configured" in str(exc):
            return {"success": True, "data": [], "status": "netbox_not_configured"}
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/credentials/{credential_id}/bind-devices")
async def bind_devices(credential_id: int, payload: DeviceBindingRequest, db: Session = Depends(get_db)):
    try:
        result = ssh_service.bind_devices(db, credential_id, payload.netbox_device_ids)
        return {"success": True, "data": result}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/credentials/{credential_id}/bindings")
async def list_bindings(credential_id: int, db: Session = Depends(get_db)):
    return {"success": True, "data": ssh_service.list_bindings(db, credential_id)}


@router.post("/connectivity-test")
async def test_connectivity(payload: ConnectivityTestRequest, db: Session = Depends(get_db)):
    try:
        result = ssh_service.test_connectivity(
            db,
            credential_id=payload.credential_id,
            netbox_device_id=payload.netbox_device_id,
        )
        return {"success": True, "data": result}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/execute-commands", deprecated=True)
async def execute_commands_disabled():
    raise HTTPException(
        status_code=410,
        detail="arbitrary SSH commands are disabled; use a registered read-only probe or an approved execution plan",
    )
