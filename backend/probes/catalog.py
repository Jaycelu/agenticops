from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProbeCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class ProbeDefinition:
    probe_id: str
    name: str
    version: str
    catalog_hash: str
    platforms: dict[str, tuple[str, ...]]
    parameters: dict[str, dict[str, Any]]


class ProbeCatalog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).with_name("templates") / "catalog.json"
        raw_bytes = self.path.read_bytes()
        payload = json.loads(raw_bytes)
        self.version = str(payload["catalog_version"])
        self.catalog_hash = hashlib.sha256(raw_bytes).hexdigest()
        self._definitions = {
            item["probe_id"]: ProbeDefinition(
                probe_id=item["probe_id"],
                name=item["name"],
                version=self.version,
                catalog_hash=self.catalog_hash,
                platforms={key: tuple(commands) for key, commands in item["platforms"].items()},
                parameters=dict(item.get("parameters") or {}),
            )
            for item in payload["probes"]
        }

    def list_public(self) -> list[dict[str, Any]]:
        return [
            {"probe_id": item.probe_id, "name": item.name, "version": item.version, "parameters": item.parameters}
            for item in sorted(self._definitions.values(), key=lambda value: value.probe_id)
        ]

    def render(self, probe_id: str, platform: str | None, parameters: dict[str, Any]) -> tuple[ProbeDefinition, list[str]]:
        definition = self._definitions.get(probe_id)
        if definition is None:
            raise ProbeCatalogError("unknown_probe")
        unknown = set(parameters) - set(definition.parameters)
        if unknown:
            raise ProbeCatalogError(f"unknown_parameters:{','.join(sorted(unknown))}")
        normalized: dict[str, str] = {}
        for name, spec in definition.parameters.items():
            value = parameters.get(name)
            if value in (None, ""):
                if spec.get("required"):
                    raise ProbeCatalogError(f"missing_parameter:{name}")
                continue
            text = str(value)
            if len(text) > 128 or not re.fullmatch(str(spec["pattern"]), text):
                raise ProbeCatalogError(f"invalid_parameter:{name}")
            normalized[name] = text
        platform_key = self._platform_key(platform)
        templates = definition.platforms.get(platform_key) or definition.platforms["default"]
        commands = [template.format_map(normalized) for template in templates]
        if any(any(char in command for char in ("\n", "\r", ";", "&&", "||", "`", "$(`", ">", "<")) for command in commands):
            raise ProbeCatalogError("unsafe_rendered_command")
        return definition, commands

    @staticmethod
    def _platform_key(platform: str | None) -> str:
        value = (platform or "").lower()
        if any(item in value for item in ("huawei", "vrp")):
            return "huawei"
        if any(item in value for item in ("h3c", "comware", "hp")):
            return "comware"
        if any(item in value for item in ("cisco", "ios", "nx-os", "arista")):
            return "cisco"
        if any(item in value for item in ("juniper", "junos")):
            return "junos"
        return "default"


probe_catalog = ProbeCatalog()
