"""命令模板服务"""
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from models.automation import CommandTemplate
from mcp.netbox_mcp import NetBoxMCP


class CommandTemplateService:
    def __init__(self):
        self.netbox = NetBoxMCP()

    def ensure_builtin_templates(self, db: Session) -> None:
        if db.query(CommandTemplate).count() > 0:
            return

        templates = [
            CommandTemplate(
                name="基础信息采集",
                template_type="diagnosis_default",
                vendor="Huawei",
                commands=[
                    "display version",
                    "display interface brief",
                    "display ip interface brief",
                    "display logbuffer | include ERROR"
                ],
                description="华为VRP常用基础诊断命令",
                is_builtin=True,
                enabled=True,
            ),
            CommandTemplate(
                name="光模块诊断",
                template_type="optics_diagnosis",
                vendor="Huawei",
                commands=[
                    "display transceiver diagnosis interface",
                    "display interface",
                    "display interface counters error"
                ],
                description="华为光模块与接口错误诊断",
                is_builtin=True,
                enabled=True,
            ),
            CommandTemplate(
                name="基础信息采集",
                template_type="diagnosis_default",
                vendor="Cisco",
                commands=[
                    "show version",
                    "show interfaces status",
                    "show ip interface brief",
                    "show logging | include ERROR|LINK|LINEPROTO"
                ],
                description="思科IOS常用基础诊断命令",
                is_builtin=True,
                enabled=True,
            ),
            CommandTemplate(
                name="光模块诊断",
                template_type="optics_diagnosis",
                vendor="Cisco",
                commands=[
                    "show interfaces transceiver",
                    "show interfaces",
                    "show controllers ethernet-controller"
                ],
                description="思科光模块与接口诊断",
                is_builtin=True,
                enabled=True,
            ),
        ]

        for t in templates:
            db.add(t)
        db.commit()

    def list_templates(self, db: Session, vendor: Optional[str] = None, template_type: Optional[str] = None) -> List[CommandTemplate]:
        self.ensure_builtin_templates(db)
        q = db.query(CommandTemplate).filter(CommandTemplate.enabled == True)
        if vendor:
            q = q.filter(CommandTemplate.vendor.ilike(f"%{vendor}%"))
        if template_type:
            q = q.filter(CommandTemplate.template_type == template_type)
        return q.order_by(CommandTemplate.vendor.asc(), CommandTemplate.template_type.asc(), CommandTemplate.name.asc()).all()

    def create_template(self, db: Session, payload: Dict[str, Any]) -> CommandTemplate:
        template = CommandTemplate(
            name=payload["name"],
            template_type=payload.get("template_type") or "diagnosis_default",
            vendor=payload["vendor"],
            commands=payload.get("commands") or [],
            description=payload.get("description"),
            is_builtin=False,
            enabled=True,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    def update_template(self, db: Session, template_id: int, payload: Dict[str, Any]) -> CommandTemplate:
        t = db.query(CommandTemplate).filter(CommandTemplate.id == template_id).first()
        if not t:
            raise ValueError("template not found")
        for k in ["name", "template_type", "vendor", "description", "enabled"]:
            if k in payload and payload[k] is not None:
                setattr(t, k, payload[k])
        if "commands" in payload and payload["commands"] is not None:
            t.commands = payload["commands"]
        db.commit()
        db.refresh(t)
        return t

    def delete_template(self, db: Session, template_id: int) -> None:
        t = db.query(CommandTemplate).filter(CommandTemplate.id == template_id).first()
        if not t:
            raise ValueError("template not found")
        db.delete(t)
        db.commit()

    async def _get_device_vendor(self, device_id: int) -> Optional[str]:
        res = await self.netbox.execute({"action": "get_device_by_id", "device_id": device_id})
        if not res.success:
            return None
        data = res.data or {}
        return data.get("manufacturer") or data.get("vendor")

    async def validate_deployment(self, db: Session, template_id: int, device_ids: List[int]) -> Dict[str, Any]:
        t = db.query(CommandTemplate).filter(CommandTemplate.id == template_id).first()
        if not t:
            raise ValueError("template not found")

        mismatched = []
        matched = []
        for device_id in device_ids:
            vendor = await self._get_device_vendor(device_id)
            if vendor and vendor.lower().find(t.vendor.lower()) >= 0:
                matched.append({"device_id": device_id, "vendor": vendor})
            else:
                mismatched.append({"device_id": device_id, "vendor": vendor})

        return {
            "template": {
                "id": t.id,
                "name": t.name,
                "vendor": t.vendor,
                "template_type": t.template_type,
            },
            "matched": matched,
            "mismatched": mismatched,
            "is_all_matched": len(mismatched) == 0,
        }

    async def resolve_commands_for_device(
        self,
        db: Session,
        device_id: int,
        template_type: str = "diagnosis_default",
    ) -> Dict[str, Any]:
        vendor = await self._get_device_vendor(device_id)
        if not vendor:
            return {"found": False, "reason": "device vendor not found", "commands": []}

        templates = self.list_templates(db, vendor=vendor, template_type=template_type)
        if not templates:
            return {
                "found": False,
                "reason": f"missing command template for vendor={vendor}, type={template_type}",
                "vendor": vendor,
                "commands": [],
            }

        t = templates[0]
        return {
            "found": True,
            "vendor": vendor,
            "template": {
                "id": t.id,
                "name": t.name,
                "template_type": t.template_type,
                "vendor": t.vendor,
                "description": t.description,
            },
            "commands": t.commands or [],
        }


command_template_service = CommandTemplateService()
