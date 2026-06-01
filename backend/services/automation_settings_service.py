"""
自动化设置管理服务。

存储模型：AutomationSetting.value (JSON) = {"mode": str, "autonomy_level": int}
- mode: 历史字段，"observe_only" | "auto"，保留向后兼容。
- autonomy_level: Phase 4 引入的 0..5 等级。

L0 OBSERVE_ONLY       全部拦（含 notification）
L1 RECOMMEND          historical observe_only：允许 notification + 观察；阻断 mutation
L2 ASSISTED           默认 'auto'：R<2 自动，R>=2 需审批
L3 GUARDED            R<3 自动
L4 AUTONOMOUS         R<4 自动
L5 SELF_OPTIMIZING    同 L4，标记自适应
"""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from config.settings import settings
from models.automation_settings import AutomationSetting
from policies.schemas import AUTONOMY_LEVEL_NAMES, AutonomyLevel


# 旧 mode -> autonomy_level 的迁移映射
_MODE_TO_LEVEL = {
    "observe_only": int(AutonomyLevel.RECOMMEND),  # L1
    "auto": int(AutonomyLevel.ASSISTED),           # L2
}


def _derive_level(value_dict: Optional[Dict[str, Any]], env_observe_only_default: bool) -> int:
    """从 stored JSON value 解析 autonomy_level；带向后兼容回退。"""
    value_dict = value_dict or {}
    if "autonomy_level" in value_dict:
        try:
            level = int(value_dict["autonomy_level"])
            if 0 <= level <= 5:
                return level
        except (TypeError, ValueError):
            pass
    mode = str(value_dict.get("mode") or "")
    if mode in _MODE_TO_LEVEL:
        return _MODE_TO_LEVEL[mode]
    return int(AutonomyLevel.RECOMMEND) if env_observe_only_default else int(AutonomyLevel.ASSISTED)


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
            value={"mode": "observe_only", "autonomy_level": int(AutonomyLevel.RECOMMEND)},
        )
        db.add(row)
        db.flush()
        return row

    # ------------------------------------------------------------------
    # autonomy_level API（Phase 4 首要入口）
    # ------------------------------------------------------------------

    def get_autonomy_level(self, db: Session) -> int:
        row = self._get_or_create_row(db, "automation_mode")
        return _derive_level(row.value, settings.automation_observe_only)

    def set_autonomy_level(self, db: Session, level: int) -> Dict[str, Any]:
        if not isinstance(level, int):
            try:
                level = int(level)
            except (TypeError, ValueError):
                raise ValueError("autonomy_level must be an integer 0..5")
        if level < 0 or level > 5:
            raise ValueError(f"autonomy_level out of range: {level}")

        row = self._get_or_create_row(db, "automation_mode")
        value = dict(row.value or {})
        value["autonomy_level"] = level
        # 同步 mode 字段，保持旧前端 / 旧消费者可用。
        value["mode"] = "observe_only" if level <= int(AutonomyLevel.RECOMMEND) else "auto"
        row.value = value
        db.add(row)
        db.commit()
        db.refresh(row)
        return self.get_automation_mode(db)

    # ------------------------------------------------------------------
    # 向后兼容的 mode API
    # ------------------------------------------------------------------

    def get_automation_mode(self, db: Session) -> Dict[str, Any]:
        """读取当前 mode + autonomy_level。返回结构保留旧字段。"""
        row = self._get_or_create_row(db, "automation_mode")
        level = _derive_level(row.value, settings.automation_observe_only)
        is_observe_only = level <= int(AutonomyLevel.RECOMMEND)
        return {
            "setting_key": "automation_mode",
            "mode": "observe_only" if is_observe_only else "auto",
            "autonomy_level": level,
            "autonomy_level_name": AUTONOMY_LEVEL_NAMES[level],
            "is_observe_only": is_observe_only,
            "description": (
                "observe_only / L0-L1: 观察模式，不执行 mutation; "
                "auto / L2+: 按 autonomy_level 自动执行（PolicyGuard 仍按 risk 分级把关）"
            ),
        }

    def set_automation_mode(self, db: Session, mode: str) -> Dict[str, Any]:
        """旧接口：observe_only / auto。内部统一转 autonomy_level。"""
        if mode not in _MODE_TO_LEVEL:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {list(_MODE_TO_LEVEL.keys())}")
        return self.set_autonomy_level(db, _MODE_TO_LEVEL[mode])

    def toggle_automation_mode(self, db: Session) -> Dict[str, Any]:
        """切换 mode（保留旧 API）。L0/L1 -> L2；其他 -> L1。"""
        current_level = self.get_autonomy_level(db)
        target = int(AutonomyLevel.ASSISTED) if current_level <= int(AutonomyLevel.RECOMMEND) else int(AutonomyLevel.RECOMMEND)
        return self.set_autonomy_level(db, target)


automation_settings_service = AutomationSettingsService()
