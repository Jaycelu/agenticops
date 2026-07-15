from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any

import paramiko
from sqlalchemy.orm import Session

from models.automation import SSHCredential, SSHCredentialDeviceBinding
from models.probe import DeviceHostKey
from services.ssh_service import ssh_service


class HostKeyRejected(RuntimeError):
    pass


def sha256_fingerprint(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected_algorithm: str, expected_fingerprint: str) -> None:
        self.expected_algorithm = expected_algorithm
        self.expected_fingerprint = expected_fingerprint

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        del client, hostname
        actual = sha256_fingerprint(key)
        if key.get_name() != self.expected_algorithm or actual != self.expected_fingerprint:
            raise HostKeyRejected("device_host_key_mismatch")


@dataclass(frozen=True)
class ProbeTarget:
    device_ip: str
    platform: str | None
    credential: SSHCredential
    host_key: DeviceHostKey


class SSHProbeTransport:
    def resolve_target(
        self,
        db: Session,
        credential_id: int,
        netbox_device_id: int,
        *,
        required_scope: str = "probe.read",
    ) -> ProbeTarget:
        binding = (
            db.query(SSHCredentialDeviceBinding)
            .filter(
                SSHCredentialDeviceBinding.credential_id == credential_id,
                SSHCredentialDeviceBinding.netbox_device_id == netbox_device_id,
            )
            .first()
        )
        if binding is None:
            raise ValueError("credential_not_bound_to_device")
        credential = db.query(SSHCredential).filter(SSHCredential.id == credential_id).first()
        if credential is None or not credential.enabled:
            raise ValueError("credential_unavailable")
        if required_scope not in (credential.capability_scope or []):
            raise ValueError(f"credential_missing_scope:{required_scope}")
        device = ssh_service._device_by_id(netbox_device_id)
        device_ip = ssh_service._extract_primary_ip(device)
        if not device_ip:
            raise ValueError("device_primary_ip_missing")
        host_key = (
            db.query(DeviceHostKey)
            .filter(
                DeviceHostKey.netbox_device_id == netbox_device_id,
                DeviceHostKey.port == credential.port,
                DeviceHostKey.active.is_(True),
            )
            .first()
        )
        if host_key is None:
            raise HostKeyRejected("device_host_key_not_registered")
        return ProbeTarget(
            device_ip=device_ip,
            platform=binding.platform,
            credential=credential,
            host_key=host_key,
        )

    def execute(self, target: ProbeTarget, commands: list[str], timeout: int) -> list[dict[str, Any]]:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(
            PinnedHostKeyPolicy(target.host_key.algorithm, target.host_key.fingerprint_sha256)
        )
        results: list[dict[str, Any]] = []
        try:
            params = ssh_service._build_connect_params(target.credential, target.device_ip, timeout=timeout)
            client.connect(**params)
            for command in commands:
                _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                output = stdout.read().decode("utf-8", errors="replace")
                error = stderr.read().decode("utf-8", errors="replace")
                exit_status = stdout.channel.recv_exit_status()
                results.append(
                    {"command": command, "output": output, "stderr": error, "exit_status": exit_status}
                )
            return results
        finally:
            client.close()


ssh_probe_transport = SSHProbeTransport()
