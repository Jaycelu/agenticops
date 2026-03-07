"""
SSH资产与凭据服务
"""
import base64
import hashlib
import io
import logging
import socket
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import paramiko
import pynetbox
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from config.settings import settings
from models.automation import SSHCredential, SSHCredentialDeviceBinding
from services.integration_config_service import integration_config_service

logger = logging.getLogger(__name__)


class SSHService:
    def _build_secret_key(self) -> bytes:
        secret = (settings.app_secret_key or "").strip()
        if not secret:
            raise ValueError("APP_SECRET_KEY is required for SSH credential encryption")
        base = f"{secret}|netops_ssh_secret"
        digest = hashlib.sha256(base.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _build_cipher(self) -> Fernet:
        return Fernet(self._build_secret_key())

    def _build_legacy_cipher(self) -> Optional[Fernet]:
        return integration_config_service.build_legacy_ssh_cipher()

    def _get_netbox_client(self):
        config = integration_config_service.get_netbox_runtime_config()
        if not config.get("enabled") or not config.get("url") or not config.get("api_token"):
            raise ValueError("netbox_not_configured")
        return pynetbox.api(config["url"], token=config["api_token"])

    def _encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        if not plaintext:
            return None
        return self._build_cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def _decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        if not ciphertext:
            return None
        try:
            return self._build_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            legacy_cipher = self._build_legacy_cipher()
            if not legacy_cipher:
                raise
            return legacy_cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    def _sanitize_credential(self, credential: SSHCredential) -> Dict[str, Any]:
        return {
            "id": credential.id,
            "name": credential.name,
            "username": credential.username,
            "auth_type": credential.auth_type,
            "port": credential.port,
            "enabled": credential.enabled,
            "created_at": credential.created_at,
            "updated_at": credential.updated_at,
            "has_password": bool(credential.encrypted_password),
            "has_private_key": bool(credential.encrypted_private_key),
        }

    def list_credentials(self, db: Session) -> List[Dict[str, Any]]:
        credentials = db.query(SSHCredential).order_by(SSHCredential.created_at.desc()).all()
        return [self._sanitize_credential(item) for item in credentials]

    def create_credential(self, db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
        auth_type = payload.get("auth_type", "password")
        if auth_type == "password" and not payload.get("password"):
            raise ValueError("password auth requires password")
        if auth_type == "private_key" and not payload.get("private_key"):
            raise ValueError("private_key auth requires private_key")

        credential = SSHCredential(
            name=payload["name"],
            username=payload["username"],
            auth_type=auth_type,
            encrypted_password=self._encrypt(payload.get("password")),
            encrypted_private_key=self._encrypt(payload.get("private_key")),
            encrypted_passphrase=self._encrypt(payload.get("passphrase")),
            port=payload.get("port", 22),
            enabled=True,
        )
        db.add(credential)
        db.commit()
        db.refresh(credential)
        return self._sanitize_credential(credential)

    def update_credential(self, db: Session, credential_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        credential = db.query(SSHCredential).filter(SSHCredential.id == credential_id).first()
        if not credential:
            raise ValueError("credential not found")

        for field in ["name", "username", "auth_type", "port", "enabled"]:
            if payload.get(field) is not None:
                setattr(credential, field, payload[field])

        if "password" in payload:
            credential.encrypted_password = self._encrypt(payload.get("password"))
        if "private_key" in payload:
            credential.encrypted_private_key = self._encrypt(payload.get("private_key"))
        if "passphrase" in payload:
            credential.encrypted_passphrase = self._encrypt(payload.get("passphrase"))

        db.commit()
        db.refresh(credential)
        return self._sanitize_credential(credential)

    def delete_credential(self, db: Session, credential_id: int) -> None:
        credential = db.query(SSHCredential).filter(SSHCredential.id == credential_id).first()
        if not credential:
            raise ValueError("credential not found")
        db.query(SSHCredentialDeviceBinding).filter(
            SSHCredentialDeviceBinding.credential_id == credential_id
        ).delete()
        db.delete(credential)
        db.commit()

    def _extract_primary_ip(self, device: Any) -> Optional[str]:
        primary_ip = str(device.primary_ip) if getattr(device, "primary_ip", None) else None
        if not primary_ip:
            return None
        return primary_ip.split("/")[0]

    def query_netbox_devices(
        self,
        site: Optional[str] = None,
        tag: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        vendor: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        nb = self._get_netbox_client()
        filters: Dict[str, Any] = {}
        if site:
            filters["site"] = site
        if tag:
            filters["tag"] = tag
        if name:
            filters["q"] = name

        devices = nb.dcim.devices.filter(**filters)
        results: List[Dict[str, Any]] = []
        for device in devices:
            device_vendor = (
                device.device_type.manufacturer.name
                if device.device_type and device.device_type.manufacturer
                else None
            )
            device_role = device.role.name if device.role else None
            model_name = device.device_type.model if device.device_type else None
            device_type_name = device.device_type.display if device.device_type else model_name

            if role and (not device_role or role.lower() not in str(device_role).lower()):
                continue
            if vendor and (not device_vendor or vendor.lower() not in str(device_vendor).lower()):
                continue
            if device_type and (not device_type_name or device_type.lower() not in str(device_type_name).lower()):
                continue

            results.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "site": device.site.name if device.site else None,
                    "role": device_role,
                    "platform": device.platform.name if device.platform else None,
                    "vendor": device_vendor,
                    "manufacturer": device_vendor,
                    "device_type": device_type_name,
                    "primary_ip": self._extract_primary_ip(device),
                    "tags": [item.name for item in device.tags] if getattr(device, "tags", None) else [],
                    "status": device.status.label if device.status else None,
                }
            )
        return results

    def bind_devices(self, db: Session, credential_id: int, netbox_device_ids: List[int]) -> Dict[str, Any]:
        credential = db.query(SSHCredential).filter(SSHCredential.id == credential_id).first()
        if not credential:
            raise ValueError("credential not found")

        devices_index = {item["id"]: item for item in self.query_netbox_devices()}
        created = 0
        updated = 0

        for device_id in netbox_device_ids:
            info = devices_index.get(device_id, {})
            binding = db.query(SSHCredentialDeviceBinding).filter(
                SSHCredentialDeviceBinding.credential_id == credential_id,
                SSHCredentialDeviceBinding.netbox_device_id == device_id,
            ).first()

            if not binding:
                binding = SSHCredentialDeviceBinding(
                    credential_id=credential_id,
                    netbox_device_id=device_id,
                )
                db.add(binding)
                created += 1
            else:
                updated += 1

            binding.device_name = info.get("name")
            binding.site_name = info.get("site")
            binding.platform = info.get("platform")
            binding.role = info.get("role")
            binding.tags = info.get("tags") or []

        db.commit()
        return {"created": created, "updated": updated, "total": len(netbox_device_ids)}

    def list_bindings(self, db: Session, credential_id: int) -> List[Dict[str, Any]]:
        bindings = db.query(SSHCredentialDeviceBinding).filter(
            SSHCredentialDeviceBinding.credential_id == credential_id
        ).order_by(SSHCredentialDeviceBinding.site_name.asc(), SSHCredentialDeviceBinding.device_name.asc()).all()
        return [
            {
                "id": item.id,
                "credential_id": item.credential_id,
                "netbox_device_id": item.netbox_device_id,
                "device_name": item.device_name,
                "site_name": item.site_name,
                "platform": item.platform,
                "role": item.role,
                "tags": item.tags or [],
                "last_connectivity_status": item.last_connectivity_status,
                "last_connectivity_error": item.last_connectivity_error,
                "last_checked_at": item.last_checked_at,
                "updated_at": item.updated_at,
            }
            for item in bindings
        ]

    def get_binding_with_credential(self, db: Session, credential_id: int, netbox_device_id: int) -> Optional[SSHCredentialDeviceBinding]:
        return db.query(SSHCredentialDeviceBinding).filter(
            SSHCredentialDeviceBinding.credential_id == credential_id,
            SSHCredentialDeviceBinding.netbox_device_id == netbox_device_id,
        ).first()

    def _build_connect_params(self, credential: SSHCredential, device_ip: str, timeout: int = 15) -> Dict[str, Any]:
        params = {
            "hostname": device_ip,
            "port": credential.port,
            "username": credential.username,
            "timeout": timeout,
            "banner_timeout": timeout,
            "auth_timeout": timeout,
            "look_for_keys": False,
            "allow_agent": False,
        }
        if credential.auth_type == "password":
            params["password"] = self._decrypt(credential.encrypted_password)
        else:
            private_key = self._decrypt(credential.encrypted_private_key)
            passphrase = self._decrypt(credential.encrypted_passphrase)
            if not private_key:
                raise ValueError("private key missing")
            params["pkey"] = self._parse_private_key(private_key, passphrase)
        return params

    def _parse_private_key(self, private_key_str: str, passphrase: Optional[str]) -> Any:
        key_readers = [
            paramiko.RSAKey.from_private_key,
            paramiko.ECDSAKey.from_private_key,
            paramiko.Ed25519Key.from_private_key,
            paramiko.DSSKey.from_private_key,
        ]
        for reader in key_readers:
            try:
                return reader(io.StringIO(private_key_str), password=passphrase)
            except Exception:
                continue
        raise ValueError("unsupported private key format")

    def _device_by_id(self, device_id: int) -> Any:
        nb = self._get_netbox_client()
        device = nb.dcim.devices.get(device_id)
        if not device:
            raise ValueError(f"netbox device not found: {device_id}")
        return device

    def test_connectivity(self, db: Session, credential_id: int, netbox_device_id: int) -> Dict[str, Any]:
        credential = db.query(SSHCredential).filter(SSHCredential.id == credential_id).first()
        if not credential:
            raise ValueError("credential not found")

        device = self._device_by_id(netbox_device_id)
        device_ip = self._extract_primary_ip(device)
        if not device_ip:
            raise ValueError("device primary ip is missing")

        status = "failed"
        message = "连接失败"
        error_detail: Optional[str] = None
        started_at = time.time()

        # 先进行TCP连通性检查
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)
        try:
            if sock.connect_ex((device_ip, credential.port)) != 0:
                status = "failed"
                message = "端口不可达"
                error_detail = "tcp_connect_failed"
                return self._persist_connectivity(
                    db,
                    credential_id,
                    netbox_device_id,
                    status,
                    message,
                    error_detail,
                    elapsed_ms=int((time.time() - started_at) * 1000),
                )
        finally:
            sock.close()

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            connect_params = self._build_connect_params(credential, device_ip)
            client.connect(**connect_params)
            status = "success"
            message = "SSH连接成功"
        except paramiko.AuthenticationException:
            status = "auth_failed"
            message = "认证失败"
            error_detail = "auth_failed"
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            message = "连接失败"
            error_detail = str(exc)
        finally:
            try:
                client.close()
            except Exception:
                pass

        return self._persist_connectivity(
            db,
            credential_id,
            netbox_device_id,
            status,
            message,
            error_detail,
            elapsed_ms=int((time.time() - started_at) * 1000),
        )

    def _persist_connectivity(
        self,
        db: Session,
        credential_id: int,
        netbox_device_id: int,
        status: str,
        message: str,
        error_detail: Optional[str],
        elapsed_ms: int,
    ) -> Dict[str, Any]:
        binding = self.get_binding_with_credential(db, credential_id, netbox_device_id)
        if not binding:
            binding = SSHCredentialDeviceBinding(
                credential_id=credential_id,
                netbox_device_id=netbox_device_id,
            )
            db.add(binding)

        binding.last_connectivity_status = status
        binding.last_connectivity_error = error_detail
        binding.last_checked_at = datetime.utcnow()
        db.commit()

        return {
            "status": status,
            "message": message,
            "error": error_detail,
            "elapsed_ms": elapsed_ms,
            "checked_at": binding.last_checked_at,
        }

    def execute_commands(
        self,
        db: Session,
        credential_id: int,
        netbox_device_id: int,
        commands: List[str],
        timeout: int = 20,
    ) -> Dict[str, Any]:
        if not commands:
            return {"success": True, "results": []}

        credential = db.query(SSHCredential).filter(SSHCredential.id == credential_id).first()
        if not credential:
            raise ValueError("credential not found")

        device = self._device_by_id(netbox_device_id)
        device_ip = self._extract_primary_ip(device)
        if not device_ip:
            raise ValueError("device primary ip is missing")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        results: List[Dict[str, Any]] = []

        try:
            connect_params = self._build_connect_params(credential, device_ip, timeout=timeout)
            client.connect(**connect_params)
            shell = client.invoke_shell()
            shell.settimeout(timeout)
            time.sleep(1)
            if shell.recv_ready():
                shell.recv(65535)

            for command in commands:
                shell.send(f"{command}\n")
                time.sleep(1.2)
                output = ""
                command_deadline = time.time() + timeout
                wait_rounds = 0
                timed_out = False
                while wait_rounds < 6 and time.time() < command_deadline:
                    time.sleep(0.5)
                    if shell.recv_ready():
                        output += shell.recv(65535).decode("utf-8", errors="ignore")
                        wait_rounds = 0
                    else:
                        wait_rounds += 1
                if time.time() >= command_deadline:
                    timed_out = True
                    try:
                        # 尝试中断当前命令，避免采集卡死
                        shell.send("\x03")
                    except Exception:
                        pass
                results.append({"command": command, "output": output.strip(), "timed_out": timed_out})

            return {"success": True, "results": results}
        finally:
            try:
                client.close()
            except Exception:
                pass

    def build_diagnostic_commands(self, platform: Optional[str], manufacturer: Optional[str]) -> List[str]:
        key = (platform or manufacturer or "").lower()

        huawei_like = [
            "display interface brief",
            "display interface",
            "display transceiver diagnosis interface",
            "display logbuffer | include ERROR",
        ]
        cisco_like = [
            "show interfaces status",
            "show interfaces",
            "show logging | include %LINK|%LINEPROTO|CRC|error",
            "show inventory",
        ]
        juniper_like = [
            "show interfaces terse",
            "show interfaces extensive",
            "show log messages | match error",
            "show chassis hardware",
        ]

        if any(v in key for v in ["huawei", "h3c", "hp comware", "comware"]):
            return huawei_like
        if any(v in key for v in ["cisco", "ios", "nx-os", "arista"]):
            return cisco_like
        if any(v in key for v in ["juniper", "junos"]):
            return juniper_like
        return [
            "show interfaces",
            "show interfaces status",
            "show logging | include error",
        ]


ssh_service = SSHService()
