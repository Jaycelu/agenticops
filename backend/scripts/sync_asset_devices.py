"""从NetBox同步设备元数据（含vendor）到本地资产表"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from mcp.netbox_mcp import NetBoxMCP
from services.asset_sync_service import asset_sync_service


async def main():
    db = SessionLocal()
    try:
        mcp = NetBoxMCP()
        result = await mcp.execute({"action": "query_devices"})
        if not result.success:
            raise RuntimeError(result.error)
        devices = result.data.get("devices", []) if isinstance(result.data, dict) else []
        summary = asset_sync_service.sync_devices(db, devices)
        print({"success": True, "summary": summary})
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
