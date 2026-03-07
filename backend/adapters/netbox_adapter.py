from typing import Any, Dict, Optional

from mcp.netbox_mcp import NetBoxMCP


class NetBoxAdapter:
    def __init__(self):
        self.client = NetBoxMCP()

    async def get_device(self, netbox_device_id: Optional[int]) -> Dict[str, Any]:
        if not netbox_device_id:
            return {"success": False, "error": "missing_netbox_device_id"}
        result = await self.client.execute({"action": "get_device_by_id", "device_id": netbox_device_id})
        return {"success": result.success, "data": result.data if result.success else {}, "error": result.error}

    async def get_topology(self, netbox_device_id: Optional[int]) -> Dict[str, Any]:
        if not netbox_device_id:
            return {"success": False, "error": "missing_netbox_device_id"}
        result = await self.client.execute({"action": "get_device_topology", "device_id": netbox_device_id})
        return {"success": result.success, "data": result.data if result.success else {}, "error": result.error}


netbox_adapter = NetBoxAdapter()

