"""
更新异常类型阈值配置
使其与采样阈值保持一致
"""
from database import SessionLocal
from models.automation import AbnormalType

def update_abnormal_type_thresholds():
    """更新异常类型阈值"""
    db = SessionLocal()

    try:
        # 查询所有启用的异常类型
        abnormal_types = db.query(AbnormalType).filter(
            AbnormalType.status == "ENABLED"
        ).all()

        # 更新阈值配置
        updated_count = 0
        for abnormal_type in abnormal_types:
            old_threshold = abnormal_type.threshold_config.copy()
            
            if abnormal_type.type_code == "LINK_QUALITY_DEGRADE":
                # CRC错误阈值：与采样阈值一致
                abnormal_type.threshold_config = {
                    "crc_error_count": 1
                }
            elif abnormal_type.type_code == "INTERFACE_FLAP":
                # Flap阈值：与采样阈值一致
                abnormal_type.threshold_config = {
                    "flap_count": 10
                }
            elif abnormal_type.type_code == "NEIGHBOR_UNSTABLE":
                # 邻居变化阈值：与采样阈值一致
                abnormal_type.threshold_config = {
                    "neighbor_change_count": 5
                }
            elif abnormal_type.type_code == "HIGH_ERROR_RATE":
                # 错误包数阈值：与采样阈值一致
                abnormal_type.threshold_config = {
                    "error_count": 5
                }
            
            if abnormal_type.threshold_config != old_threshold:
                print(f"✓ 更新 {abnormal_type.type_code}: {old_threshold} -> {abnormal_type.threshold_config}")
                updated_count += 1

        db.commit()
        print(f"\n更新完成！共更新 {updated_count} 个异常类型")

    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_abnormal_type_thresholds()