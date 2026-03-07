"""
ELK 日志范围配置与解析服务。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from models.log_scope import LogScope
from services.integration_config_service import integration_config_service


class LogScopeService:
    def _normalize(self, value: Optional[str]) -> str:
        return (value or "").strip().lower()

    def _serialize(self, scope: LogScope) -> Dict[str, Any]:
        return {
            "id": scope.id,
            "scope_key": scope.scope_key,
            "display_name": scope.display_name,
            "netbox_site_id": scope.netbox_site_id,
            "site_code_snapshot": scope.site_code_snapshot,
            "site_name_snapshot": scope.site_name_snapshot,
            "aliases": list(scope.aliases or []),
            "query_filter": scope.query_filter,
            "default_time_range": scope.default_time_range,
            "enabled": scope.enabled,
            "sort_order": scope.sort_order,
            "scope_metadata": dict(scope.scope_metadata or {}),
            "updated_at": scope.updated_at.isoformat() if scope.updated_at else None,
        }

    def _query(self, db: Session):
        return db.query(LogScope).order_by(LogScope.sort_order.asc(), LogScope.id.asc())

    def list_scopes(self, db: Session | None = None, *, enabled_only: bool = False) -> list[Dict[str, Any]]:
        def _load(target_db: Session) -> list[Dict[str, Any]]:
            query = self._query(target_db)
            if enabled_only:
                query = query.filter(LogScope.enabled.is_(True))
            return [self._serialize(scope) for scope in query.all()]

        if db is not None:
            return _load(db)
        local_db = SessionLocal()
        try:
            return _load(local_db)
        finally:
            local_db.close()

    def get_scope(self, db: Session, scope_id: int) -> Dict[str, Any]:
        scope = db.query(LogScope).filter(LogScope.id == scope_id).first()
        if scope is None:
            raise ValueError("log scope not found")
        return self._serialize(scope)

    def create_scope(self, db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
        scope = LogScope(**self._sanitize_payload(payload))
        db.add(scope)
        db.commit()
        db.refresh(scope)
        return self._serialize(scope)

    def update_scope(self, db: Session, scope_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        scope = db.query(LogScope).filter(LogScope.id == scope_id).first()
        if scope is None:
            raise ValueError("log scope not found")
        sanitized = self._sanitize_payload(payload)
        for key, value in sanitized.items():
            setattr(scope, key, value)
        db.commit()
        db.refresh(scope)
        return self._serialize(scope)

    def delete_scope(self, db: Session, scope_id: int) -> None:
        scope = db.query(LogScope).filter(LogScope.id == scope_id).first()
        if scope is None:
            raise ValueError("log scope not found")
        db.delete(scope)
        db.commit()

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        aliases = [
            alias.strip()
            for alias in (payload.get("aliases") or [])
            if str(alias or "").strip()
        ]
        return {
            "scope_key": str(payload.get("scope_key") or "").strip(),
            "display_name": str(payload.get("display_name") or "").strip(),
            "netbox_site_id": payload.get("netbox_site_id"),
            "site_code_snapshot": str(payload.get("site_code_snapshot") or "").strip() or None,
            "site_name_snapshot": str(payload.get("site_name_snapshot") or "").strip() or None,
            "aliases": aliases,
            "query_filter": str(payload.get("query_filter") or "").strip(),
            "default_time_range": str(payload.get("default_time_range") or "-1d,now").strip() or "-1d,now",
            "enabled": bool(payload.get("enabled", True)),
            "sort_order": int(payload.get("sort_order", 100)),
            "scope_metadata": payload.get("scope_metadata") or {},
        }

    def _iter_candidates(self, scope: Dict[str, Any]) -> Iterable[str]:
        yield self._normalize(scope.get("scope_key"))
        yield self._normalize(scope.get("display_name"))
        yield self._normalize(scope.get("site_code_snapshot"))
        yield self._normalize(scope.get("site_name_snapshot"))
        for alias in scope.get("aliases") or []:
            yield self._normalize(alias)

    def resolve_scope(
        self,
        *,
        db: Session | None = None,
        scope_key: Optional[str] = None,
        base_name: Optional[str] = None,
        netbox_site_id: Optional[int] = None,
        site_code: Optional[str] = None,
        site_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        tokens = [
            self._normalize(scope_key),
            self._normalize(base_name),
            self._normalize(site_code),
            self._normalize(site_name),
        ]
        tokens = [token for token in tokens if token]

        def _resolve(target_db: Session) -> Optional[Dict[str, Any]]:
            scopes = self.list_scopes(target_db, enabled_only=True)
            if netbox_site_id is not None:
                for scope in scopes:
                    if scope.get("netbox_site_id") == netbox_site_id:
                        return scope
            for token in tokens:
                for scope in scopes:
                    if token in set(self._iter_candidates(scope)):
                        return scope
            return None

        if db is not None:
            return _resolve(db)

        local_db = SessionLocal()
        try:
            return _resolve(local_db)
        finally:
            local_db.close()

    async def test_scope(self, db: Session, scope_id: int) -> Dict[str, Any]:
        scope = db.query(LogScope).filter(LogScope.id == scope_id).first()
        if scope is None:
            raise ValueError("log scope not found")
        config = integration_config_service.get_elk_runtime_config(db=db)
        if not config.get("enabled") or not config.get("url"):
            return {"success": False, "message": "ELK 未配置或未启用", "details": {}}

        import base64

        credentials = f"{config.get('username', '')}:{config.get('password', '')}"
        auth_header = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        params = {
            "domain": "ops",
            "time_range": scope.default_time_range,
            "operator": "admin",
            "query": scope.query_filter,
            "category": "search",
            "background": "false",
            "highlight": "false",
            "fields": "false",
            "timeline": "false",
            "size": "1",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    config["url"],
                    headers={"Authorization": f"Basic {auth_header}"},
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
            total_hits = payload.get("results", {}).get("total_hits", payload.get("total", 0))
            return {
                "success": True,
                "message": "日志范围测试成功",
                "details": {
                    "scope_key": scope.scope_key,
                    "display_name": scope.display_name,
                    "total_hits": total_hits,
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "message": f"日志范围测试失败: {exc}",
                "details": {"scope_key": scope.scope_key},
            }

    def list_bound_site_codes(self, db: Session | None = None) -> list[str]:
        def _load(target_db: Session) -> list[str]:
            rows = (
                target_db.query(LogScope.site_code_snapshot)
                .filter(LogScope.enabled.is_(True))
                .filter(LogScope.site_code_snapshot.isnot(None))
                .all()
            )
            return sorted({str(row[0]).upper() for row in rows if row[0]})

        if db is not None:
            return _load(db)
        local_db = SessionLocal()
        try:
            return _load(local_db)
        finally:
            local_db.close()


log_scope_service = LogScopeService()
