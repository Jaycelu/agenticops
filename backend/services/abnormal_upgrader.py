"""
异常升级规则服务
将单次事件升级为状态异常，避免误报
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from database import SessionLocal
from models.automation import LogSample, Site
from config.site_config import get_sampling_thresholds

logger = logging.getLogger(__name__)


class AbnormalUpgrader:
    """异常升级器"""

    def __init__(self):
        pass

    def _get_thresholds_by_site_id(self, db: Session, site_id: int) -> Dict:
        """根据site_id动态获取阈值，避免硬编码基地。"""
        site = db.query(Site).filter(Site.id == site_id).first()
        site_code = site.site_code if site and site.site_code else "DEYANG"
        thresholds = get_sampling_thresholds(site_code)
        if thresholds:
            return thresholds
        return {
            "crc_error_threshold": 10,
            "flap_threshold": 3,
            "neighbor_change_threshold": 2,
            "error_count_threshold": 100
        }

    def check_upgrade_needed(
        self,
        site_id: int,
        netbox_device_id: Optional[int] = None,
        check_window_minutes: int = 30
    ) -> Dict:
        """
        检查是否需要将单次事件升级为状态异常

        Args:
            site_id: 基地ID
            netbox_device_id: 设备ID（可选）
            check_window_minutes: 检查窗口（分钟）

        Returns:
            升级检查结果
        """
        db = SessionLocal()

        try:
            # 计算时间范围
            time_end = datetime.now()
            time_start = time_end - timedelta(minutes=check_window_minutes)

            # 构建查询
            query = db.query(LogSample).filter(
                LogSample.site_id == site_id,
                LogSample.sampled_at >= time_start,
                LogSample.sampled_at <= time_end
            )

            if netbox_device_id:
                query = query.filter(LogSample.netbox_device_id == netbox_device_id)

            # 获取采样数据
            samples = query.order_by(LogSample.sampled_at).all()

            if not samples:
                return {
                    "needs_upgrade": False,
                    "reason": "No samples in check window"
                }

            # 获取阈值配置
            thresholds = self._get_thresholds_by_site_id(db, site_id)

            # 检查各类异常的升级条件
            upgrade_checks = {
                "crc_upgrade": self._check_crc_upgrade(samples, thresholds),
                "flap_upgrade": self._check_flap_upgrade(samples, thresholds),
                "neighbor_upgrade": self._check_neighbor_upgrade(samples, thresholds),
                "error_upgrade": self._check_error_upgrade(samples, thresholds)
            }

            # 判断是否需要升级
            needs_upgrade = any(check["meets_criteria"] for check in upgrade_checks.values())

            # 确定异常类型
            abnormal_type = None
            if needs_upgrade:
                if upgrade_checks["crc_upgrade"]["meets_criteria"]:
                    abnormal_type = "LINK_QUALITY_DEGRADE"
                elif upgrade_checks["flap_upgrade"]["meets_criteria"]:
                    abnormal_type = "INTERFACE_FLAP"
                elif upgrade_checks["neighbor_upgrade"]["meets_criteria"]:
                    abnormal_type = "NEIGHBOR_UNSTABLE"
                elif upgrade_checks["error_upgrade"]["meets_criteria"]:
                    abnormal_type = "HIGH_ERROR_RATE"

            return {
                "needs_upgrade": needs_upgrade,
                "abnormal_type": abnormal_type,
                "check_window": {
                    "start": time_start.isoformat(),
                    "end": time_end.isoformat(),
                    "minutes": check_window_minutes
                },
                "upgrade_checks": upgrade_checks,
                "summary": {
                    "total_samples": len(samples),
                    "abnormal_samples": len([s for s in samples if s.is_abnormal])
                }
            }

        except Exception as e:
            logger.error(f"Error checking upgrade needed: {e}", exc_info=True)
            raise
        finally:
            db.close()

    def _check_crc_upgrade(self, samples: List[LogSample], thresholds: Dict) -> Dict:
        """
        检查CRC错误升级条件

        升级规则：
        1. 连续3个采样周期都有CRC错误
        2. CRC错误数持续增长
        3. 平均CRC错误数超过阈值

        Args:
            samples: 采样数据列表
            thresholds: 阈值配置

        Returns:
            CRC升级检查结果
        """
        crc_samples = [s for s in samples if s.crc_error_count > 0]

        if len(crc_samples) < 3:
            return {
                "meets_criteria": False,
                "reason": f"Only {len(crc_samples)} samples with CRC errors (need at least 3)"
            }

        # 检查是否连续
        is_consecutive = self._check_consecutive_samples(crc_samples, samples)

        # 检查趋势
        crc_values = [s.crc_error_count for s in crc_samples]
        avg_crc = sum(crc_values) / len(crc_values)
        is_increasing = crc_values[-1] > crc_values[0]

        # 判断是否满足升级条件
        meets_criteria = is_consecutive and is_increasing and avg_crc >= thresholds["crc_error_threshold"]

        return {
            "meets_criteria": meets_criteria,
            "is_consecutive": is_consecutive,
            "is_increasing": is_increasing,
            "avg_crc": avg_crc,
            "threshold": thresholds["crc_error_threshold"],
            "reason": f"CRC errors {'are consecutive and increasing' if meets_criteria else 'do not meet upgrade criteria'}"
        }

    def _check_flap_upgrade(self, samples: List[LogSample], thresholds: Dict) -> Dict:
        """
        检查接口flap升级条件

        升级规则：
        1. 在检查窗口内flap次数超过阈值
        2. flap频率持续较高

        Args:
            samples: 采样数据列表
            thresholds: 阈值配置

        Returns:
            Flap升级检查结果
        """
        flap_samples = [s for s in samples if s.flap_count > 0]

        if not flap_samples:
            return {
                "meets_criteria": False,
                "reason": "No flap samples found"
            }

        total_flaps = sum(s.flap_count for s in flap_samples)

        # 判断是否满足升级条件
        meets_criteria = total_flaps >= thresholds["flap_threshold"] * len(flap_samples)

        return {
            "meets_criteria": meets_criteria,
            "total_flaps": total_flaps,
            "threshold_per_sample": thresholds["flap_threshold"],
            "expected_threshold": thresholds["flap_threshold"] * len(flap_samples),
            "reason": f"Total flaps: {total_flaps} {'meets' if meets_criteria else 'does not meet'} upgrade criteria"
        }

    def _check_neighbor_upgrade(self, samples: List[LogSample], thresholds: Dict) -> Dict:
        """
        检查邻居变化升级条件

        升级规则：
        1. 邻居变化次数超过阈值
        2. 邻居变化持续发生

        Args:
            samples: 采样数据列表
            thresholds: 阈值配置

        Returns:
            邻居升级检查结果
        """
        neighbor_samples = [s for s in samples if s.neighbor_change_count > 0]

        if not neighbor_samples:
            return {
                "meets_criteria": False,
                "reason": "No neighbor change samples found"
            }

        total_changes = sum(s.neighbor_change_count for s in neighbor_samples)

        # 判断是否满足升级条件
        meets_criteria = total_changes >= thresholds["neighbor_change_threshold"]

        return {
            "meets_criteria": meets_criteria,
            "total_changes": total_changes,
            "threshold": thresholds["neighbor_change_threshold"],
            "reason": f"Total neighbor changes: {total_changes} {'meets' if meets_criteria else 'does not meet'} upgrade criteria"
        }

    def _check_error_upgrade(self, samples: List[LogSample], thresholds: Dict) -> Dict:
        """
        检查错误数升级条件

        升级规则：
        1. 总错误数超过阈值
        2. 错误率持续较高

        Args:
            samples: 采样数据列表
            thresholds: 阈值配置

        Returns:
            错误升级检查结果
        """
        error_samples = [s for s in samples if s.error_count > 0]

        if not error_samples:
            return {
                "meets_criteria": False,
                "reason": "No error samples found"
            }

        total_errors = sum(s.error_count for s in error_samples)
        avg_errors = total_errors / len(error_samples)

        # 判断是否满足升级条件
        meets_criteria = total_errors >= thresholds["error_count_threshold"]

        return {
            "meets_criteria": meets_criteria,
            "total_errors": total_errors,
            "avg_errors": avg_errors,
            "threshold": thresholds["error_count_threshold"],
            "reason": f"Total errors: {total_errors} {'meets' if meets_criteria else 'does not meet'} upgrade criteria"
        }

    def _check_consecutive_samples(
        self,
        filtered_samples: List[LogSample],
        all_samples: List[LogSample]
    ) -> bool:
        """
        检查采样是否连续

        Args:
            filtered_samples: 过滤后的采样列表
            all_samples: 所有采样列表

        Returns:
            是否连续
        """
        if len(filtered_samples) < 2:
            return True

        # 检查过滤后的采样在原始列表中的索引是否连续
        indices = [all_samples.index(s) for s in filtered_samples]
        indices.sort()

        # 检查索引是否连续（允许间隔1个采样）
        for i in range(1, len(indices)):
            if indices[i] - indices[i-1] > 2:
                return False

        return True


# 全局异常升级器实例
abnormal_upgrader = AbnormalUpgrader()
