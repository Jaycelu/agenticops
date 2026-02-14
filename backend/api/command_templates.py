from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from api.schemas.command_template import (
    CommandTemplateCreateRequest,
    CommandTemplateResolveRequest,
    CommandTemplateUpdateRequest,
    CommandTemplateValidateRequest,
)
from services.command_template_service import command_template_service

router = APIRouter(prefix="/api/command-templates", tags=["command-templates"])


@router.get("")
async def list_templates(
    vendor: str | None = Query(default=None),
    template_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    items = command_template_service.list_templates(db, vendor=vendor, template_type=template_type)
    return {
        "success": True,
        "data": [
            {
                "id": i.id,
                "name": i.name,
                "template_type": i.template_type,
                "vendor": i.vendor,
                "commands": i.commands,
                "description": i.description,
                "is_builtin": i.is_builtin,
                "enabled": i.enabled,
                "created_at": i.created_at,
                "updated_at": i.updated_at,
            }
            for i in items
        ],
    }


@router.post("")
async def create_template(payload: CommandTemplateCreateRequest, db: Session = Depends(get_db)):
    item = command_template_service.create_template(db, payload.model_dump())
    return {"success": True, "data": {"id": item.id}}


@router.put("/{template_id}")
async def update_template(template_id: int, payload: CommandTemplateUpdateRequest, db: Session = Depends(get_db)):
    try:
        item = command_template_service.update_template(db, template_id, payload.model_dump(exclude_unset=True))
        return {"success": True, "data": {"id": item.id}}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{template_id}")
async def delete_template(template_id: int, db: Session = Depends(get_db)):
    try:
        command_template_service.delete_template(db, template_id)
        return {"success": True}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/validate-deployment")
async def validate_deployment(payload: CommandTemplateValidateRequest, db: Session = Depends(get_db)):
    try:
        result = await command_template_service.validate_deployment(db, payload.template_id, payload.device_ids)
        return {"success": True, "data": result}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/resolve")
async def resolve_template(payload: CommandTemplateResolveRequest, db: Session = Depends(get_db)):
    result = await command_template_service.resolve_commands_for_device(
        db,
        device_id=payload.device_id,
        template_type=payload.template_type,
    )
    return {"success": True, "data": result}
