from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from config.settings import settings


class TicketAdapter:
    """Adapter for integrating with an existing ticket system."""

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.ticket_system_api_key:
            headers["Authorization"] = f"Bearer {settings.ticket_system_api_key}"
        return headers

    async def create_ticket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.ticket_system_base_url:
            # Fallback mock mode for local integration until real API is configured.
            return {
                "success": True,
                "ticket_id": f"LOCAL-{int(datetime.now().timestamp())}",
                "status": "created",
                "provider": "mock",
            }

        url = f"{settings.ticket_system_base_url.rstrip('/')}/tickets"
        async with httpx.AsyncClient(timeout=settings.ticket_system_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return {
                "success": True,
                "ticket_id": str(data.get("ticket_id") or data.get("id") or ""),
                "status": str(data.get("status") or "created"),
                "provider": "external",
                "raw": data,
            }

    async def update_ticket(self, ticket_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.ticket_system_base_url:
            return {"success": True, "ticket_id": ticket_id, "status": payload.get("status", "updated"), "provider": "mock"}

        url = f"{settings.ticket_system_base_url.rstrip('/')}/tickets/{ticket_id}"
        async with httpx.AsyncClient(timeout=settings.ticket_system_timeout_seconds) as client:
            resp = await client.patch(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return {
                "success": True,
                "ticket_id": ticket_id,
                "status": str(data.get("status") or payload.get("status") or "updated"),
                "provider": "external",
                "raw": data,
            }


ticket_adapter = TicketAdapter()
