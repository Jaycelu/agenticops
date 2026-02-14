"""
更新现有自动化任务的device_ip信息
从任务代码中提取IP地址并更新到decision_result的context中
"""
import re
from database import SessionLocal
from models.automation import AutomationTask
from sqlalchemy.orm.attributes import flag_modified


def extract_ip_from_task_code(task_code: str) -> str:
    """
    从任务代码中提取IP地址

    任务代码格式：TASK_{site_id}_{ip_with_underscores}_{timestamp}
    例如：TASK_1_10_128_243_65_1768359964 -> 10.128.243.65
    """
    # 移除TASK_前缀和timestamp
    parts = task_code.split('_')
    if len(parts) >= 4 and parts[0] == 'TASK':
        # 跳过TASK和site_id，提取IP部分（倒数第二部分之前的所有部分）
        ip_parts = parts[2:-1]
        if len(ip_parts) >= 4:
            # 确保是有效的IP地址（4个部分）
            try:
                ip = '.'.join(ip_parts)
                # 验证IP地址格式
                parts_check = ip.split('.')
                if len(parts_check) == 4 and all(0 <= int(p) <= 255 for p in parts_check):
                    return ip
            except (ValueError, IndexError):
                pass
    return None


def update_task_device_ips():
    """更新所有任务的device_ip"""
    db = SessionLocal()

    try:
        # 查询所有任务
        tasks = db.query(AutomationTask).all()

        updated_count = 0
        skipped_count = 0

        for task in tasks:
            # 检查是否已经有device_ip
            if task.decision_result and "context" in task.decision_result:
                if "device_ip" in task.decision_result["context"]:
                    skipped_count += 1
                    continue

            # 从任务代码中提取IP
            device_ip = extract_ip_from_task_code(task.task_code)

            if device_ip:
                # 更新decision_result
                if not task.decision_result:
                    task.decision_result = {}

                if "context" not in task.decision_result:
                    task.decision_result["context"] = {}

                task.decision_result["context"]["device_ip"] = device_ip
                task.decision_result["context"]["site_id"] = task.site_id
                if task.netbox_device_id:
                    task.decision_result["context"]["netbox_device_id"] = task.netbox_device_id

                # 标记decision_result字段已修改
                flag_modified(task, "decision_result")

                updated_count += 1
                print(f"✓ 更新任务 {task.id}: {task.task_code} -> {device_ip}")
            else:
                print(f"✗ 无法提取IP: {task.task_code}")

        db.commit()

        print(f"\n更新完成！")
        print(f"已更新: {updated_count} 个任务")
        print(f"已跳过: {skipped_count} 个任务（已有device_ip）")

    except Exception as e:
        db.rollback()
        print(f"更新失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    update_task_device_ips()
