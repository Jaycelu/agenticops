"""基地自动化开关服务"""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models.automation import Site, SiteAutomationSwitch


class SiteAutomationService:
    def _default_enabled(self, site: Site) -> bool:
        return (site.site_code or "").upper() == "DEYANG"

    def ensure_switch_rows(self, db: Session) -> None:
        sites = db.query(Site).all()
        if not sites:
            return

        existing = {
            row.site_id: row
            for row in db.query(SiteAutomationSwitch).filter(
                SiteAutomationSwitch.site_id.in_([s.id for s in sites])
            ).all()
        }

        created = False
        for site in sites:
            if site.id in existing:
                continue
            db.add(SiteAutomationSwitch(site_id=site.id, enabled=self._default_enabled(site)))
            created = True

        if created:
            db.commit()

    def get_site_enabled_map(self, db: Session) -> Dict[int, bool]:
        self.ensure_switch_rows(db)
        rows = db.query(SiteAutomationSwitch).all()
        return {row.site_id: bool(row.enabled) for row in rows}

    def is_site_enabled(
        self,
        db: Session,
        site_id: Optional[int] = None,
        site_code: Optional[str] = None,
    ) -> bool:
        self.ensure_switch_rows(db)

        if site_id is not None:
            row = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.site_id == site_id).first()
            return bool(row.enabled) if row else False

        if site_code:
            site = db.query(Site).filter(Site.site_code == site_code.upper()).first()
            if not site:
                return site_code.upper() == "DEYANG"
            row = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.site_id == site.id).first()
            if row:
                return bool(row.enabled)
            return self._default_enabled(site)

        return False

    def get_enabled_site_ids(self, db: Session) -> List[int]:
        self.ensure_switch_rows(db)
        rows = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.enabled == True).all()
        return [row.site_id for row in rows]

    def set_site_enabled(self, db: Session, site_id: int, enabled: bool) -> bool:
        self.ensure_switch_rows(db)
        row = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.site_id == site_id).first()
        if not row:
            row = SiteAutomationSwitch(site_id=site_id, enabled=enabled)
            db.add(row)
        else:
            row.enabled = enabled
        db.commit()
        return bool(enabled)


site_automation_service = SiteAutomationService()
