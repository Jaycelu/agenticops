from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.site_automation_service import site_automation_service
from auth.dependencies import require_permissions
from auth.rbac import Permission

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("")
async def list_sites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return site_automation_service.list_sites_view(db, skip=skip, limit=limit)


@router.get("/{site_id}")
async def get_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    payload = site_automation_service.get_site_view(db, site_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return payload


@router.put(
    "/{site_id}/automation-toggle",
    dependencies=[Depends(require_permissions(Permission.AUTOMATION_MANAGE.value))],
)
async def toggle_site_automation(
    site_id: int,
    enabled: bool,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = site_automation_service.get_site_view(db, site_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Site not found")
    site_automation_service.set_site_enabled(db, site_id, enabled)

    async def _refresh_sampler_safely():
        try:
            from services.log_sampler import log_sampler

            await log_sampler.refresh_jobs()
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Failed to refresh log sampler after site toggle")

    background_tasks.add_task(_refresh_sampler_safely)
    return {"site_id": site_id, "enabled": bool(enabled), "refresh_scheduled": True}
