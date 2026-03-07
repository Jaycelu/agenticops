from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.automation import SSHCredentialDeviceBinding
from services.ssh_service import ssh_service


class SSHAdapter:
    def resolve_credential_id(self, db: Session, netbox_device_id: Optional[int]) -> Optional[int]:
        if not netbox_device_id:
            return None
        binding = (
            db.query(SSHCredentialDeviceBinding)
            .filter(SSHCredentialDeviceBinding.netbox_device_id == netbox_device_id)
            .order_by(SSHCredentialDeviceBinding.last_checked_at.desc().nullslast())
            .first()
        )
        return binding.credential_id if binding else None

    def collect_command_evidence(
        self,
        db: Session,
        *,
        netbox_device_id: Optional[int],
        credential_id: Optional[int] = None,
        platform: Optional[str] = None,
        manufacturer: Optional[str] = None,
        commands: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not netbox_device_id:
            return {"success": False, "error": "missing_netbox_device_id"}
        effective_credential_id = credential_id or self.resolve_credential_id(db, netbox_device_id)
        if not effective_credential_id:
            return {"success": False, "error": "missing_ssh_binding"}
        command_list = commands or ssh_service.build_diagnostic_commands(platform, manufacturer)
        try:
            result = ssh_service.execute_commands(
                db,
                credential_id=effective_credential_id,
                netbox_device_id=netbox_device_id,
                commands=command_list,
            )
            return {
                "success": bool(result.get("success")),
                "credential_id": effective_credential_id,
                "commands": command_list,
                "results": result.get("results", []),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "credential_id": effective_credential_id,
                "commands": command_list,
                "error": str(exc),
            }


ssh_adapter = SSHAdapter()

