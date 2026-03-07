import re
from typing import Any, Dict, List, Optional

from mcp.elk_mcp import ELKMCP


IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DEVIP = re.compile(r"(?:DevIP|devip)=((?:\d{1,3}\.){3}\d{1,3})")
RAW_DEVICE = re.compile(r"^<\d+>\w+\s+\d+\s+\d+\s+\d+:\d+:\d+\s+([^\s]+)")
UUID = re.compile(r"\b[0-9a-fA-F\-]{36}\b")
HEX = re.compile(r"0x[0-9a-fA-F]+")
NUM = re.compile(r"\b\d+\b")
SPACE = re.compile(r"\s+")


class ELKAdapter:
    def __init__(self):
        self.client = ELKMCP()

    @staticmethod
    def is_ipv4(value: str) -> bool:
        return bool(IPV4.fullmatch(value or ""))

    def extract_device_ip(self, row: Dict[str, Any], raw: str) -> str:
        hostname = (row.get("hostname") or "").strip()
        if self.is_ipv4(hostname):
            return hostname
        match = DEVIP.search(raw or "")
        if match:
            ip = match.group(1)
            if self.is_ipv4(ip):
                return ip
        return row.get("device_ip") or ""

    def extract_device_name(self, row: Dict[str, Any], raw: str) -> str:
        match = RAW_DEVICE.search(raw or "")
        if match:
            name = match.group(1)
            if not self.is_ipv4(name):
                return name
        hostname = (row.get("hostname") or "").strip()
        if hostname and not self.is_ipv4(hostname):
            return hostname
        return ""

    @staticmethod
    def normalize_signature(message: str) -> str:
        text = (message or "").lower()
        text = UUID.sub("<uuid>", text)
        text = HEX.sub("<hex>", text)
        text = NUM.sub("<n>", text)
        text = SPACE.sub(" ", text).strip()
        return text[:200]

    async def collect_logs(
        self,
        *,
        base_name: Optional[str] = None,
        query: Optional[str] = None,
        time_range: str = "-15m,now",
        limit: int = 200,
    ) -> Dict[str, Any]:
        if base_name:
            result = await self.client.execute(
                {
                    "action": "query_logs_by_base",
                    "base_name": base_name,
                    "time_range": time_range,
                    "limit": limit,
                }
            )
        else:
            result = await self.client.execute(
                {
                    "action": "query_logs",
                    "query": query or "*",
                    "time_range": time_range,
                    "limit": limit,
                    "offset": 0,
                }
            )
        if not result.success:
            return {"success": False, "error": result.error or "ELK unavailable", "logs": []}
        return {"success": True, **(result.data or {})}

    def aggregate_logs(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        devices: Dict[str, Dict[str, Any]] = {}
        total_logs = 0

        for row in logs:
            total_logs += 1
            raw = (row.get("message") or row.get("raw_message") or "")[:1000]
            device_ip = self.extract_device_ip(row, raw)
            device_name = self.extract_device_name(row, raw)
            signature = self.normalize_signature(raw)
            if not device_ip:
                device_ip = "unknown"

            bucket = devices.setdefault(
                device_ip,
                {
                    "device_ip": device_ip,
                    "device_name": device_name,
                    "total_logs": 0,
                    "signatures": {},
                },
            )
            bucket["total_logs"] += 1
            sig = bucket["signatures"].setdefault(signature, {"count": 0, "example": raw[:300]})
            sig["count"] += 1

        device_list = []
        for device in devices.values():
            signatures = sorted(
                device["signatures"].items(),
                key=lambda item: item[1]["count"],
                reverse=True,
            )
            device_list.append(
                {
                    "device_ip": device["device_ip"],
                    "device_name": device["device_name"],
                    "total_logs": device["total_logs"],
                    "top_signatures": [
                        {
                            "signature": signature,
                            "count": info["count"],
                            "example": info["example"],
                        }
                        for signature, info in signatures[:20]
                    ],
                }
            )
        device_list.sort(key=lambda item: item["total_logs"], reverse=True)

        return {
            "summary": {
                "total_logs": total_logs,
                "devices_with_logs": len(device_list),
            },
            "devices": device_list,
        }


elk_adapter = ELKAdapter()

