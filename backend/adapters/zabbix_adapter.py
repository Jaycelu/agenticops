from typing import Any, Dict, Optional

import httpx

from services.integration_config_service import integration_config_service


class ZabbixAdapter:
    def _get_runtime_config(self) -> Dict[str, Any]:
        return integration_config_service.get_zabbix_runtime_config()

    @property
    def available(self) -> bool:
        config = self._get_runtime_config()
        return bool(
            config.get("enabled")
            and (config.get("api_url") or config.get("url"))
            and config.get("username")
            and config.get("password")
        )

    async def get_recent_alerts(
        self,
        *,
        host: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        config = self._get_runtime_config()
        url = config.get("api_url") or config.get("url")
        if not (config.get("enabled") and url and config.get("username") and config.get("password")):
            return {"success": False, "error": "zabbix_not_configured", "alerts": []}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                login_payload = {
                    "jsonrpc": "2.0",
                    "method": "user.login",
                    "params": {
                        "username": config["username"],
                        "password": config["password"],
                    },
                    "id": 1,
                }
                login_resp = await client.post(url, json=login_payload)
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
                resp = await client.post(url, json=problem_payload)
                resp.raise_for_status()
                result = resp.json().get("result") or []
                return {"success": True, "alerts": result}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc), "alerts": []}


zabbix_adapter = ZabbixAdapter()
