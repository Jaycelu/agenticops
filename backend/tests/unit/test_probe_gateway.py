from __future__ import annotations

import base64

import paramiko
import pytest

from api.probes import HostKeyRegistration
from probes.catalog import ProbeCatalogError, probe_catalog
from probes.redaction import redact_output
from probes.ssh_transport import HostKeyRejected, PinnedHostKeyPolicy, sha256_fingerprint


pytestmark = pytest.mark.unit


def test_probe_catalog_renders_only_registered_templates() -> None:
    definition, commands = probe_catalog.render(
        "network.interface_status", "Cisco IOS", {"interface": "GigabitEthernet0/1"}
    )

    assert definition.probe_id == "network.interface_status"
    assert commands == ["show interface GigabitEthernet0/1"]
    with pytest.raises(ProbeCatalogError, match="unknown_probe"):
        probe_catalog.render("shell.command", "Cisco IOS", {})


@pytest.mark.parametrize(
    "value",
    [
        "GigabitEthernet0/1\nconfigure terminal",
        "Gi0/1;reload",
        "Gi0/1|include secret",
        "$(reboot)",
        "Gi0/1 > startup-config",
    ],
)
def test_probe_parameters_reject_command_injection(value: str) -> None:
    with pytest.raises(ProbeCatalogError, match="invalid_parameter"):
        probe_catalog.render("network.interface_status", "Cisco IOS", {"interface": value})


def test_probe_output_is_redacted_before_bounding() -> None:
    value, count, truncated = redact_output(
        "username netops\npassword super-secret\nsnmp-server community public RO\n" + "x" * 100,
        max_bytes=80,
    )

    assert "super-secret" not in value
    assert " community public" not in value
    assert count == 2
    assert truncated is True


def test_pinned_host_key_policy_rejects_mismatch() -> None:
    expected = paramiko.RSAKey.generate(1024)
    unexpected = paramiko.RSAKey.generate(1024)
    policy = PinnedHostKeyPolicy(expected.get_name(), sha256_fingerprint(expected))

    with pytest.raises(HostKeyRejected, match="mismatch"):
        policy.missing_host_key(paramiko.SSHClient(), "device", unexpected)
    policy.missing_host_key(paramiko.SSHClient(), "device", expected)


def test_host_key_registration_schema_rejects_extra_fields() -> None:
    key = paramiko.RSAKey.generate(1024)
    payload = HostKeyRegistration.model_validate(
        {
            "netbox_device_id": 7,
            "hostname": "edge-01",
            "algorithm": key.get_name(),
            "public_key_base64": base64.b64encode(key.asbytes()).decode("ascii"),
        }
    )
    assert payload.netbox_device_id == 7
    with pytest.raises(ValueError):
        HostKeyRegistration.model_validate({**payload.model_dump(), "trust_on_first_use": True})


def test_arbitrary_ssh_endpoint_is_closed_by_contract() -> None:
    from api.ssh_management import execute_commands_disabled

    with pytest.raises(Exception) as exc_info:
        import asyncio

        asyncio.run(execute_commands_disabled())
    assert getattr(exc_info.value, "status_code", None) == 410
