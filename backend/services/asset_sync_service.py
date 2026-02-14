"""资产同步服务：将NetBox设备元数据镜像到本地表"""
from datetime import datetime
from typing import Dict, List, Any

from sqlalchemy.orm import Session

from models.automation import AssetDevice


class AssetSyncService:
    def sync_devices(self, db: Session, devices: List[Dict[str, Any]]) -> Dict[str, int]:
        created = 0
        updated = 0

        for item in devices:
            netbox_device_id = item.get("id")
            if not netbox_device_id:
                continue

            record = db.query(AssetDevice).filter(AssetDevice.netbox_device_id == netbox_device_id).first()
            if not record:
                record = AssetDevice(netbox_device_id=netbox_device_id)
                db.add(record)
                created += 1
            else:
                updated += 1

            record.name = item.get("name")
            record.device_type = item.get("device_type")
            record.site = item.get("site")
            record.role = item.get("role")
            record.vendor = item.get("vendor") or item.get("manufacturer")
            record.status = item.get("status")
            record.serial = item.get("serial")
            record.primary_ip = item.get("primary_ip")
            record.rack = item.get("rack")
            record.position = str(item.get("position") or "")
            record.face = item.get("face")
            record.tags = item.get("tags") or []
            record.last_synced_at = datetime.now()

        db.commit()
        return {"created": created, "updated": updated, "total": len(devices)}


asset_sync_service = AssetSyncService()
