"""
异常类型管理服务
管理异常类型的配置和状态
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from database import SessionLocal
from models.automation import AbnormalType, AbnormalTypeStatus

logger = logging.getLogger(__name__)


class AbnormalTypeService:
    """异常类型管理服务"""

    def __init__(self):
        self._default_types_initialized = False

    def _initialize_default_types(self, db: Session):
        """初始化默认异常类型"""
        if self._default_types_initialized:
            return

        # 检查是否已存在默认类型
        existing_count = db.query(AbnormalType).filter(
            AbnormalType.status == AbnormalTypeStatus.ENABLED
        ).count()

        if existing_count > 0:
            self._default_types_initialized = True
            return

        # 创建默认异常类型
        default_types = [
            {
                "type_code": "LINK_QUALITY_DEGRADE",
                "type_name": "链路质量下降",
                "description": "CRC错误次数过多，表示链路质量下降",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["CRC", "error"],
                "threshold_config": {
                    "crc_error_count": 100,
                    "time_window_minutes": 30
                },
                "risk_level": "high",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 2,
                    "dedup_window_minutes": 120,
                    "cooldown_minutes": 120
                }
            },
            {
                "type_code": "INTERFACE_FLAP",
                "type_name": "接口震荡",
                "description": "接口频繁up/down，表示接口不稳定",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["flap", "linkDown", "linkUp"],
                "threshold_config": {
                    "flap_count": 50,
                    "time_window_minutes": 30
                },
                "risk_level": "high",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 2,
                    "dedup_window_minutes": 120,
                    "cooldown_minutes": 120
                }
            },
            {
                "type_code": "NEIGHBOR_UNSTABLE",
                "type_name": "邻居不稳定",
                "description": "邻居关系频繁变化，表示邻居不稳定",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["neighbor", "change", "down"],
                "threshold_config": {
                    "neighbor_change_count": 50,
                    "time_window_minutes": 30
                },
                "risk_level": "medium",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 2,
                    "dedup_window_minutes": 120,
                    "cooldown_minutes": 120
                }
            },
            {
                "type_code": "HIGH_ERROR_RATE",
                "type_name": "高错误率",
                "description": "错误日志数量过多，表示设备运行异常",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["error", "critical", "alert"],
                "threshold_config": {
                    "error_count": 1000,
                    "time_window_minutes": 30
                },
                "risk_level": "medium",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 2,
                    "dedup_window_minutes": 120,
                    "cooldown_minutes": 120
                }
            }
        ]

        for type_data in default_types:
            abnormal_type = AbnormalType(**type_data)
            db.add(abnormal_type)

        db.commit()
        self._default_types_initialized = True
        logger.info(f"Initialized {len(default_types)} default abnormal types")

    def get_enabled_types(self, db: Session) -> List[AbnormalType]:
        """获取所有启用的异常类型"""
        self._initialize_default_types(db)
        return db.query(AbnormalType).filter(
            AbnormalType.status == AbnormalTypeStatus.ENABLED
        ).all()

    def get_type_by_code(self, db: Session, type_code: str) -> Optional[AbnormalType]:
        """根据类型代码获取异常类型"""
        self._initialize_default_types(db)
        return db.query(AbnormalType).filter(
            AbnormalType.type_code == type_code
        ).first()

    def match_abnormal_type(
        self,
        db: Session,
        error_count: int,
        crc_error_count: int,
        flap_count: int,
        neighbor_change_count: int,
        other_error_count: int,
        other_error_fingerprints: List[str]
    ) -> Optional[Dict]:
        """
        匹配异常类型

        Args:
            db: 数据库会话
            error_count: 错误数量
            crc_error_count: CRC错误数量
            flap_count: 接口flap数量
            neighbor_change_count: 邻居变化数量
            other_error_count: 其他错误数量
            other_error_fingerprints: 其他错误指纹列表

        Returns:
            匹配的异常类型信息，如果没有匹配则返回None
        """
        enabled_types = self.get_enabled_types(db)

        # 按优先级匹配
        for abnormal_type in enabled_types:
            threshold_config = abnormal_type.threshold_config
            
            # 根据类型代码匹配
            if abnormal_type.type_code == "LINK_QUALITY_DEGRADE":
                threshold = threshold_config.get("crc_error_count", threshold_config.get("count", 1))
                if crc_error_count >= threshold:
                    return {
                        "type_code": abnormal_type.type_code,
                        "type_name": abnormal_type.type_name,
                        "risk_level": abnormal_type.risk_level,
                        "enable_tracking": abnormal_type.enable_tracking,
                        "tracking_config": abnormal_type.tracking_config
                    }
            elif abnormal_type.type_code == "INTERFACE_FLAP":
                threshold = threshold_config.get("flap_count", threshold_config.get("count", 10))
                if flap_count >= threshold:
                    return {
                        "type_code": abnormal_type.type_code,
                        "type_name": abnormal_type.type_name,
                        "risk_level": abnormal_type.risk_level,
                        "enable_tracking": abnormal_type.enable_tracking,
                        "tracking_config": abnormal_type.tracking_config
                    }
            elif abnormal_type.type_code == "NEIGHBOR_UNSTABLE":
                threshold = threshold_config.get("neighbor_change_count", threshold_config.get("count", 5))
                if neighbor_change_count >= threshold:
                    return {
                        "type_code": abnormal_type.type_code,
                        "type_name": abnormal_type.type_name,
                        "risk_level": abnormal_type.risk_level,
                        "enable_tracking": abnormal_type.enable_tracking,
                        "tracking_config": abnormal_type.tracking_config
                    }
            elif abnormal_type.type_code == "HIGH_ERROR_RATE":
                threshold = threshold_config.get("error_count", threshold_config.get("count", 5))
                if error_count >= threshold:
                    return {
                        "type_code": abnormal_type.type_code,
                        "type_name": abnormal_type.type_name,
                        "risk_level": abnormal_type.risk_level,
                        "enable_tracking": abnormal_type.enable_tracking,
                        "tracking_config": abnormal_type.tracking_config
                    }

        # 检查是否有其他类型的错误
        if other_error_count >= 20:  # 默认阈值
            # 使用指纹来识别具体的异常类型
            if other_error_fingerprints:
                fingerprint = other_error_fingerprints[0]
                return {
                    "type_code": f"UNKNOWN_{fingerprint[:20]}",
                    "type_name": f"未知异常 ({fingerprint[:20]})",
                    "risk_level": "medium",
                    "enable_tracking": True,
                    "tracking_config": {
                        "accumulation_threshold": 2,
                        "dedup_window_minutes": 120,
                        "cooldown_minutes": 120
                    }
                }

        return None

    def update_occurrence(self, db: Session, type_code: str):
        """更新异常类型的出现次数"""
        abnormal_type = self.get_type_by_code(db, type_code)
        if abnormal_type:
            abnormal_type.occurrence_count += 1
            abnormal_type.last_occurred_at = datetime.now()
            db.commit()


# 全局异常类型服务实例
abnormal_type_service = AbnormalTypeService()
