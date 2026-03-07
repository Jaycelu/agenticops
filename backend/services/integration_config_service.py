"""
外部集成配置中心。
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict

import httpx
import pynetbox
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from config.settings import settings
from database import SessionLocal
from models.integration_settings import IntegrationSetting


class IntegrationConfigService:
    INTEGRATIONS: dict[str, dict[str, Any]] = {
        "netbox": {
            "display_name": "NetBox",
            "config_fields": ["url"],
            "secret_fields": ["api_token"],
            "env": {
                "url": "netbox_url",
                "api_token": "netbox_api_token",
            },
        },
        "elk": {
            "display_name": "ELK",
            "config_fields": ["url"],
            "secret_fields": ["username", "password"],
            "env": {
                "url": "elk_url",
                "username": "elk_username",
                "password": "elk_password",
            },
        },
        "zabbix": {
            "display_name": "Zabbix",
            "config_fields": ["url", "api_url"],
            "secret_fields": ["username", "password"],
            "env": {
                "url": "zabbix_url",
                "api_url": "zabbix_api_url",
                "username": "zabbix_username",
                "password": "zabbix_password",
            },
        },
    }

    def _get_spec(self, integration_type: str) -> dict[str, Any]:
        spec = self.INTEGRATIONS.get(integration_type)
        if not spec:
            raise ValueError(f"unsupported integration type: {integration_type}")
        return spec

    def _is_configured(self, integration_type: str, values: dict[str, Any]) -> bool:
        if integration_type == "zabbix":
            return bool(
                (values.get("api_url") or values.get("url"))
                and values.get("username")
                and values.get("password")
            )
        spec = self._get_spec(integration_type)
        return bool(
            all(values.get(field) for field in spec["config_fields"])
            and all(values.get(field) for field in spec["secret_fields"])
        )

    def _build_cipher(self) -> Fernet:
        secret = (settings.app_secret_key or "").strip()
        if not secret:
            raise ValueError("APP_SECRET_KEY is required for encrypted integration settings")
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def _encrypt_value(self, plaintext: str) -> str:
        if plaintext == "":
            return ""
        return self._build_cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def _decrypt_value(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        return self._build_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    def _get_row(self, db: Session, integration_type: str) -> IntegrationSetting | None:
        return (
            db.query(IntegrationSetting)
            .filter(IntegrationSetting.integration_type == integration_type)
            .first()
        )

    def _get_or_create_row(self, db: Session, integration_type: str) -> IntegrationSetting:
        spec = self._get_spec(integration_type)
        row = self._get_row(db, integration_type)
        if row:
            return row
        row = IntegrationSetting(
            integration_type=integration_type,
            display_name=spec["display_name"],
            enabled=False,
            config={},
            secrets_encrypted={},
        )
        db.add(row)
        db.flush()
        return row

    def _mask_secret_status(self, spec: dict[str, Any], secrets: dict[str, str]) -> dict[str, bool]:
        return {field: bool(secrets.get(field)) for field in spec["secret_fields"]}

    def _format_response(
        self,
        integration_type: str,
        enabled: bool,
        config: dict[str, Any],
        secrets: dict[str, str],
        *,
        updated_at: Any = None,
        source: str = "database",
    ) -> dict[str, Any]:
        spec = self._get_spec(integration_type)
        return {
            "integration_type": integration_type,
            "display_name": spec["display_name"],
            "enabled": enabled,
            "config": {field: config.get(field, "") for field in spec["config_fields"]},
            "secret_status": self._mask_secret_status(spec, secrets),
            "updated_at": updated_at.isoformat() if updated_at else None,
            "source": source,
        }

    def list_public_configs(self, db: Session) -> list[dict[str, Any]]:
        return [self.get_public_config(db, integration_type) for integration_type in self.INTEGRATIONS]

    def get_public_config(self, db: Session, integration_type: str) -> dict[str, Any]:
        spec = self._get_spec(integration_type)
        row = self._get_row(db, integration_type)
        if row:
            return self._format_response(
                integration_type,
                row.enabled,
                row.config or {},
                row.secrets_encrypted or {},
                updated_at=row.updated_at,
            )

        env_values = {
            key: getattr(settings, env_name, "") or ""
            for key, env_name in spec["env"].items()
        }
        env_config = {field: env_values.get(field, "") for field in spec["config_fields"]}
        env_secrets = {field: env_values.get(field, "") for field in spec["secret_fields"]}
        enabled = self._is_configured(integration_type, env_values)
        return self._format_response(
            integration_type,
            enabled,
            env_config,
            env_secrets,
            source="env" if enabled else "default",
        )

    def upsert_config(
        self,
        db: Session,
        integration_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        spec = self._get_spec(integration_type)
        row = self._get_or_create_row(db, integration_type)
        row.display_name = spec["display_name"]
        row.enabled = bool(payload.get("enabled", row.enabled))

        config_payload = payload.get("config") or {}
        secret_payload = payload.get("secrets") or {}
        clear_secrets = set(payload.get("clear_secrets") or [])

        config = dict(row.config or {})
        for field in spec["config_fields"]:
            if field in config_payload:
                config[field] = str(config_payload.get(field) or "").strip()
        row.config = config

        encrypted = dict(row.secrets_encrypted or {})
        for field in spec["secret_fields"]:
            if field in clear_secrets:
                encrypted.pop(field, None)
                continue
            if field in secret_payload:
                value = str(secret_payload.get(field) or "").strip()
                if value:
                    encrypted[field] = self._encrypt_value(value)
        row.secrets_encrypted = encrypted

        db.add(row)
        db.commit()
        db.refresh(row)
        return self._format_response(
            integration_type,
            row.enabled,
            row.config or {},
            row.secrets_encrypted or {},
            updated_at=row.updated_at,
        )

    def get_runtime_config(self, integration_type: str, *, db: Session | None = None) -> dict[str, Any]:
        spec = self._get_spec(integration_type)

        def _load(target_db: Session) -> dict[str, Any]:
            row = self._get_row(target_db, integration_type)
            if row:
                config = dict(row.config or {})
                decrypted_secrets: dict[str, str] = {}
                for field, encrypted_value in (row.secrets_encrypted or {}).items():
                    try:
                        decrypted_secrets[field] = self._decrypt_value(encrypted_value)
                    except InvalidToken as exc:
                        raise ValueError(
                            f"{integration_type} secret decryption failed, check APP_SECRET_KEY"
                        ) from exc
                return {
                    "enabled": row.enabled,
                    **config,
                    **decrypted_secrets,
                }

            env_values = {
                key: getattr(settings, env_name, "") or ""
                for key, env_name in spec["env"].items()
            }
            enabled = self._is_configured(integration_type, env_values)
            return {"enabled": enabled, **env_values}

        if db is not None:
            return _load(db)

        local_db = SessionLocal()
        try:
            return _load(local_db)
        finally:
            local_db.close()

    def get_netbox_runtime_config(self) -> dict[str, Any]:
        return self.get_runtime_config("netbox")

    def get_elk_runtime_config(self) -> dict[str, Any]:
        return self.get_runtime_config("elk")

    def get_zabbix_runtime_config(self) -> dict[str, Any]:
        return self.get_runtime_config("zabbix")

    def build_legacy_ssh_cipher(self) -> Fernet | None:
        netbox_token = self.get_netbox_runtime_config().get("api_token", "")
        if not netbox_token:
            return None
        base = f"{settings.database_url}|{netbox_token}|netops_ssh_secret"
        digest = hashlib.sha256(base.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    async def test_config(self, integration_type: str, *, db: Session | None = None) -> dict[str, Any]:
        config = self.get_runtime_config(integration_type, db=db)
        if not config.get("enabled"):
            return {"success": False, "message": f"{integration_type} 未启用或未配置", "details": {}}

        if integration_type == "netbox":
            try:
                client = pynetbox.api(config["url"], token=config["api_token"])
                list(client.dcim.sites.filter(limit=1))
                return {"success": True, "message": "NetBox 连接成功", "details": {"url": config["url"]}}
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "message": f"NetBox 连接失败: {exc}", "details": {"url": config["url"]}}

        if integration_type == "elk":
            auth_header = base64.b64encode(
                f"{config['username']}:{config['password']}".encode("utf-8")
            ).decode("utf-8")
            params = {
                "domain": "ops",
                "time_range": "-5m,now",
                "operator": "admin",
                "query": "*",
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
                return {"success": True, "message": "ELK 连接成功", "details": {"url": config["url"]}}
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "message": f"ELK 连接失败: {exc}", "details": {"url": config["url"]}}

        if integration_type == "zabbix":
            url = config.get("api_url") or config.get("url")
            login_payload = {
                "jsonrpc": "2.0",
                "method": "user.login",
                "params": {
                    "username": config["username"],
                    "password": config["password"],
                },
                "id": 1,
            }
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(url, json=login_payload)
                    response.raise_for_status()
                    token = response.json().get("result")
                if not token:
                    return {"success": False, "message": "Zabbix 登录失败", "details": {"url": url}}
                return {"success": True, "message": "Zabbix 连接成功", "details": {"url": url}}
            except Exception as exc:  # noqa: BLE001
                return {"success": False, "message": f"Zabbix 连接失败: {exc}", "details": {"url": url}}

        return {"success": False, "message": f"unsupported integration type: {integration_type}", "details": {}}


integration_config_service = IntegrationConfigService()
