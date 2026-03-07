from typing import Any, Dict, Optional

import httpx

from config.settings import settings


class ZabbixAdapter:
    def __init__(self):
        self.url = settings.zabbix_api_url or settings.zabbix_url
        self.username = settings.zabbix_username
        self.password = settings.zabbix_password

    @property
    def available(self) -> bool:
        return bool(self.url and self.username and self.password)

    async def get_recent_alerts(
        self,
        *,
        host: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        if not self.available:
            return {"success": False, "error": "zabbix_not_configured", "alerts": []}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                login_payload = {
                    "jsonrpc": "2.0",
                    "method": "user.login",
                    "params": {
                        "username": self.username,
                        "password": self.password,
                    },
                    "id": 1,
                }
                login_resp = await client.post(self.url, json=login_payload)
                login_resp.raise_for_status()
                token = login_resp.json().get("result")
                if not token:
                    return {"success": False, "error": "zabbix_login_failed", "alerts": []}

                params: Dict[str, Any] = {
                    "output": "extend",
                    "selectHosts": ["host", "name"],
                    "sortfield": ["clock", "eventid"],
                    "sortorder": "DESC",
                    "limit": limit,
                    "value": 1,
                }
                if host:
                    params["search"] = {"name": host}

                problem_payload = {
                    "jsonrpc": "2.0",
                    "method": "problem.get",
                    "params": params,
                    "auth": token,
                    "id": 2,
                }
                resp = await client.post(self.url, json=problem_payload)
                resp.raise_for_status()
                result = resp.json().get("result") or []
                return {"success": True, "alerts": result}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc), "alerts": []}


zabbix_adapter = ZabbixAdapter()
