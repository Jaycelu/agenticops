"""
初始化默认异常类型数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.automation import AbnormalType, AbnormalTypeStatus
from datetime import datetime

def init_default_abnormal_types():
    """初始化默认异常类型"""
    db = SessionLocal()
    
    try:
        # 检查是否已经初始化过
        existing_count = db.query(AbnormalType).count()
        if existing_count > 0:
            print(f"数据库中已有 {existing_count} 个异常类型，跳过初始化")
            return
        
        # 定义默认异常类型
        default_types = [
            {
                "type_code": "LINK_QUALITY_DEGRADE",
                "type_name": "链路质量下降",
                "description": "CRC错误过多，表明链路质量下降",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["CRC", "crc", "error", "quality"],
                "threshold_config": {
                    "crc_error_count": 50
                },
                "risk_level": "high",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 5,
                    "dedup_window_minutes": 60,
                    "cooldown_minutes": 60
                }
            },
            {
                "type_code": "INTERFACE_FLAP",
                "type_name": "接口震荡",
                "description": "接口状态频繁变化，表明接口不稳定",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["flap", "down", "up", "interface"],
                "threshold_config": {
                    "flap_count": 20
                },
                "risk_level": "high",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 5,
                    "dedup_window_minutes": 60,
                    "cooldown_minutes": 60
                }
            },
            {
                "type_code": "NEIGHBOR_UNSTABLE",
                "type_name": "邻居不稳定",
                "description": "邻居关系频繁变化，表明邻居不稳定",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["neighbor", "change", "down", "lldp"],
                "threshold_config": {
                    "neighbor_change_count": 20
                },
                "risk_level": "medium",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 5,
                    "dedup_window_minutes": 60,
                    "cooldown_minutes": 60
                }
            },
            {
                "type_code": "HIGH_ERROR_RATE",
                "type_name": "高错误率",
                "description": "错误日志数量过多，表明设备可能存在问题",
                "status": AbnormalTypeStatus.ENABLED,
                "keywords": ["error", "critical", "alert"],
                "threshold_config": {
                    "error_count": 500
                },
                "risk_level": "medium",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 5,
                    "dedup_window_minutes": 60,
                    "cooldown_minutes": 60
                }
            },
            {
                "type_code": "UNKNOWN_ERROR",
                "type_name": "未知错误",
                "description": "其他类型的错误日志",
                "status": AbnormalTypeStatus.OBSERVED,
                "keywords": [],
                "threshold_config": {
                    "other_error_count": 10
                },
                "risk_level": "low",
                "enable_tracking": True,
                "tracking_config": {
                    "accumulation_threshold": 5,
                    "dedup_window_minutes": 60,
                    "cooldown_minutes": 60
                }
            }
        ]
        
        # 创建异常类型
        for type_data in default_types:
            abnormal_type = AbnormalType(
                type_code=type_data["type_code"],
                type_name=type_data["type_name"],
                description=type_data["description"],
                status=type_data["status"],
                keywords=type_data["keywords"],
                threshold_config=type_data["threshold_config"],
                risk_level=type_data["risk_level"],
                enable_tracking=type_data["enable_tracking"],
                tracking_config=type_data["tracking_config"],
                created_by="system",
                updated_by="system"
            )
            db.add(abnormal_type)
            print(f"创建异常类型: {type_data['type_code']} - {type_data['type_name']}")
        
        db.commit()
        print(f"\n成功初始化 {len(default_types)} 个默认异常类型")
        
    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_default_abnormal_types()
