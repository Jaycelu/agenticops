"""基地自动化开关服务"""
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.automation import Site, SiteAutomationSwitch


class SiteAutomationService:
    def _ensure_switch_table(self, db: Session) -> None:
        """
        对历史数据库做兼容：缺少site_automation_switch表时自动创建。
        """
        try:
            bind = db.get_bind()
            SiteAutomationSwitch.__table__.create(bind=bind, checkfirst=True)
        except Exception:
            # 建表失败时交由上层降级处理
            pass

    def _default_enabled(self, site: Site) -> bool:
        return (site.site_code or "").upper() == "DEYANG"

    def ensure_switch_rows(self, db: Session) -> None:
        self._ensure_switch_table(db)
        sites = db.query(Site).all()
        if not sites:
            return

        try:
            existing = {
                row.site_id: row
                for row in db.query(SiteAutomationSwitch).filter(
                    SiteAutomationSwitch.site_id.in_([s.id for s in sites])
                ).all()
            }
        except SQLAlchemyError:
            # 表或列异常时不阻断主流程，退化为默认开关
            existing = {}

        created = False
        for site in sites:
            if site.id in existing:
                continue
            db.add(SiteAutomationSwitch(site_id=site.id, enabled=self._default_enabled(site)))
            created = True

        if created:
            db.commit()

    def get_site_enabled_map(self, db: Session) -> Dict[int, bool]:
        try:
            self.ensure_switch_rows(db)
            rows = db.query(SiteAutomationSwitch).all()
            if rows:
                return {row.site_id: bool(row.enabled) for row in rows}
        except SQLAlchemyError:
            pass

        # 数据库结构异常时，回退到默认策略，避免前端整页不可用
        sites = db.query(Site).all()
        return {site.id: self._default_enabled(site) for site in sites}

    def is_site_enabled(
        self,
        db: Session,
        site_id: Optional[int] = None,
        site_code: Optional[str] = None,
    ) -> bool:
        self.ensure_switch_rows(db)

        if site_id is not None:
            try:
                row = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.site_id == site_id).first()
                return bool(row.enabled) if row else False
            except SQLAlchemyError:
                site = db.query(Site).filter(Site.id == site_id).first()
                return self._default_enabled(site) if site else False

        if site_code:
            site = db.query(Site).filter(Site.site_code == site_code.upper()).first()
            if not site:
                return site_code.upper() == "DEYANG"
            try:
                row = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.site_id == site.id).first()
                if row:
                    return bool(row.enabled)
            except SQLAlchemyError:
                return self._default_enabled(site)
            return self._default_enabled(site)

        return False

    def get_enabled_site_ids(self, db: Session) -> List[int]:
        try:
            self.ensure_switch_rows(db)
            rows = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.enabled == True).all()
            return [row.site_id for row in rows]
        except SQLAlchemyError:
            sites = db.query(Site).all()
            return [site.id for site in sites if self._default_enabled(site)]

    def set_site_enabled(self, db: Session, site_id: int, enabled: bool) -> bool:
        try:
            self.ensure_switch_rows(db)
            row = db.query(SiteAutomationSwitch).filter(SiteAutomationSwitch.site_id == site_id).first()
            if not row:
                row = SiteAutomationSwitch(site_id=site_id, enabled=enabled)
                db.add(row)
            else:
                row.enabled = enabled
            db.commit()
            return bool(enabled)
        except SQLAlchemyError:
            # 降级返回，避免前端无响应
            return bool(enabled)

    def list_sites_view(self, db: Session, *, skip: int = 0, limit: int = 100) -> Dict[str, object]:
        sites = db.query(Site).offset(skip).limit(limit).all()
        enabled_map = self.get_site_enabled_map(db)
        return {
            "total": db.query(Site).count(),
            "sites": [
                {
                    "id": site.id,
                    "site_code": site.site_code,
                    "site_name": site.site_name,
                    "description": site.description,
                    "automation_enabled": enabled_map.get(site.id, False),
                }
                for site in sites
            ],
        }

    def get_site_view(self, db: Session, site_id: int) -> Optional[Dict[str, object]]:
        site = db.query(Site).filter(Site.id == site_id).first()
        if not site:
            return None
        enabled_map = self.get_site_enabled_map(db)
        return {
            "id": site.id,
            "site_code": site.site_code,
            "site_name": site.site_name,
            "description": site.description,
            "automation_enabled": enabled_map.get(site.id, False),
        }


site_automation_service = SiteAutomationService()
