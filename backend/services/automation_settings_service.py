"""
自动化设置管理服务。
"""
from typing import Any, Dict

from sqlalchemy.orm import Session

from config.settings import settings
from models.automation_settings import AutomationSetting


class AutomationSettingsService:
    """管理自动化相关的系统设置"""

    def _get_or_create_row(self, db: Session, setting_key: str) -> AutomationSetting:
        row = (
            db.query(AutomationSetting)
            .filter(AutomationSetting.setting_key == setting_key)
            .first()
        )
        if row:
            return row

        display_names = {
            "automation_mode": "自动化模式",
        }

        row = AutomationSetting(
            setting_key=setting_key,
            display_name=display_names.get(setting_key, setting_key),
            value={"mode": "observe_only"},
        )
        db.add(row)
        db.flush()
        return row

    def get_automation_mode(self, db: Session) -> Dict[str, Any]:
        """获取当前自动化模式"""
        row = self._get_or_create_row(db, "automation_mode")
        mode_value = row.value.get("mode", "observe_only")

        # 如果没有明确设置，使用环境变量的默认值
        if mode_value == "default":
            mode_value = "observe_only" if settings.automation_observe_only else "auto"

        return {
            "setting_key": "automation_mode",
            "mode": mode_value,
            "is_observe_only": mode_value == "observe_only",
            "description": "observe_only: 观察模式，只读分析不执行; auto: 自动模式，自动创建Case并执行Agent",
        }

    def set_automation_mode(self, db: Session, mode: str) -> Dict[str, Any]:
        """设置自动化模式"""
        valid_modes = ["observe_only", "auto"]

        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

        row = self._get_or_create_row(db, "automation_mode")
        row.value = {"mode": mode}
        db.add(row)
        db.commit()
        db.refresh(row)

        return self.get_automation_mode(db)

    def toggle_automation_mode(self, db: Session) -> Dict[str, Any]:
        """切换自动化模式"""
        current = self.get_automation_mode(db)
        new_mode = "auto" if current["mode"] == "observe_only" else "observe_only"
        return self.set_automation_mode(db, new_mode)


automation_settings_service = AutomationSettingsService()