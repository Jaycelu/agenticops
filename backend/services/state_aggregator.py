"""
状态聚合服务
分析多个时间窗口的日志采样数据，识别趋势性异常
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, String

from database import SessionLocal
from models.automation import LogSample, Site
from config.site_config import get_sampling_thresholds

logger = logging.getLogger(__name__)


class StateAggregator:
    """状态聚合器"""

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
            "neighbor_change_threshold": 2
        }

    def aggregate_device_state(
        self,
        site_id: int,
        netbox_device_id: Optional[int] = None,
        device_ip: Optional[str] = None,
        time_window_hours: int = 24
    ) -> Dict:
        """
        聚合设备状态

        Args:
            site_id: 基地ID
            netbox_device_id: 设备ID（可选）
            device_ip: 设备IP（可选，当netbox_device_id为None时使用）
            time_window_hours: 时间窗口（小时）

        Returns:
            聚合状态字典
        """
        db = SessionLocal()

        try:
            # 计算时间范围
            time_end = datetime.now()
            time_start = time_end - timedelta(hours=time_window_hours)

            # 构建查询
            query = db.query(LogSample).filter(
                LogSample.site_id == site_id,
                LogSample.sampled_at >= time_start,
                LogSample.sampled_at <= time_end
            )

            # 优先使用netbox_device_id过滤，如果没有则使用device_ip
            if netbox_device_id:
                query = query.filter(LogSample.netbox_device_id == netbox_device_id)
            elif device_ip:
                # 使用JSON查询device_ip
                query = query.filter(LogSample.raw_data.op('->>')('device_ip') == device_ip)

            # 按采样时间排序
            samples = query.order_by(LogSample.sampled_at).all()

            if not samples:
                return {
                    "has_data": False,
                    "message": "No samples found in the time window"
                }

            # 聚合统计
            total_samples = len(samples)
            abnormal_samples = [s for s in samples if s.is_abnormal]

            # CRC错误趋势
            crc_trend = self._analyze_crc_trend(samples)

            # Flap频率分析
            flap_frequency = self._analyze_flap_frequency(samples)

            # 邻居变化分析
            neighbor_stability = self._analyze_neighbor_stability(samples)

            # 判断是否需要升级为状态异常
            thresholds = self._get_thresholds_by_site_id(db, site_id)
            is_state_abnormal, abnormal_type = self._check_state_abnormal(
                crc_trend,
                flap_frequency,
                neighbor_stability,
                thresholds
            )

            return {
                "has_data": True,
                "time_window": {
                    "start": time_start.isoformat(),
                    "end": time_end.isoformat(),
                    "hours": time_window_hours
                },
                "summary": {
                    "total_samples": total_samples,
                    "abnormal_samples": len(abnormal_samples),
                    "abnormal_rate": len(abnormal_samples) / total_samples if total_samples > 0 else 0
                },
                "crc_trend": crc_trend,
                "flap_frequency": flap_frequency,
                "neighbor_stability": neighbor_stability,
                "state_abnormal": {
                    "is_abnormal": is_state_abnormal,
                    "abnormal_type": abnormal_type
                }
            }

        except Exception as e:
            logger.error(f"Error aggregating device state: {e}", exc_info=True)
            raise
        finally:
            db.close()

    def _analyze_crc_trend(self, samples: List[LogSample]) -> Dict:
        """
        分析CRC错误趋势

        Args:
            samples: 采样数据列表

        Returns:
            CRC趋势分析结果
        """
        crc_values = [s.crc_error_count for s in samples if s.crc_error_count > 0]

        if not crc_values:
            return {
                "has_crc_errors": False,
                "trend": "stable",
                "description": "No CRC errors detected"
            }

        # 计算趋势
        if len(crc_values) >= 3:
            # 简单线性趋势判断
            first_half = crc_values[:len(crc_values)//2]
            second_half = crc_values[len(crc_values)//2:]

            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)

            if avg_second > avg_first * 1.5:
                trend = "increasing"
                description = f"CRC errors are increasing (avg: {avg_first:.1f} → {avg_second:.1f})"
            elif avg_second < avg_first * 0.5:
                trend = "decreasing"
                description = f"CRC errors are decreasing (avg: {avg_first:.1f} → {avg_second:.1f})"
            else:
                trend = "stable"
                description = f"CRC errors are stable (avg: {avg_first:.1f})"
        else:
            trend = "insufficient_data"
            description = "Insufficient data to determine trend"

        return {
            "has_crc_errors": True,
            "trend": trend,
            "description": description,
            "max_crc": max(crc_values),
            "avg_crc": sum(crc_values) / len(crc_values),
            "total_crc": sum(crc_values)
        }

    def _analyze_flap_frequency(self, samples: List[LogSample]) -> Dict:
        """
        分析接口flap频率

        Args:
            samples: 采样数据列表

        Returns:
            Flap频率分析结果
        """
        flap_values = [s.flap_count for s in samples if s.flap_count > 0]

        if not flap_values:
            return {
                "has_flaps": False,
                "frequency": "none",
                "description": "No interface flaps detected"
            }

        # 计算flap频率（每小时）
        time_span_hours = (samples[-1].sampled_at - samples[0].sampled_at).total_seconds() / 3600
        if time_span_hours > 0:
            flaps_per_hour = sum(flap_values) / time_span_hours
        else:
            flaps_per_hour = 0

        # 判断频率等级
        if flaps_per_hour > 10:
            frequency = "high"
            description = f"High flap frequency: {flaps_per_hour:.1f} flaps/hour"
        elif flaps_per_hour > 2:
            frequency = "medium"
            description = f"Medium flap frequency: {flaps_per_hour:.1f} flaps/hour"
        else:
            frequency = "low"
            description = f"Low flap frequency: {flaps_per_hour:.1f} flaps/hour"

        return {
            "has_flaps": True,
            "frequency": frequency,
            "description": description,
            "flaps_per_hour": flaps_per_hour,
            "total_flaps": sum(flap_values),
            "max_flaps_in_sample": max(flap_values)
        }

    def _analyze_neighbor_stability(self, samples: List[LogSample]) -> Dict:
        """
        分析邻居稳定性

        Args:
            samples: 采样数据列表

        Returns:
            邻居稳定性分析结果
        """
        neighbor_changes = [s.neighbor_change_count for s in samples if s.neighbor_change_count > 0]

        if not neighbor_changes:
            return {
                "has_changes": False,
                "stability": "stable",
                "description": "No neighbor changes detected"
            }

        # 计算变化频率（每小时）
        time_span_hours = (samples[-1].sampled_at - samples[0].sampled_at).total_seconds() / 3600
        if time_span_hours > 0:
            changes_per_hour = sum(neighbor_changes) / time_span_hours
        else:
            changes_per_hour = 0

        # 判断稳定性
        if changes_per_hour > 5:
            stability = "unstable"
            description = f"Unstable neighbors: {changes_per_hour:.1f} changes/hour"
        elif changes_per_hour > 1:
            stability = "fluctuating"
            description = f"Fluctuating neighbors: {changes_per_hour:.1f} changes/hour"
        else:
            stability = "stable"
            description = f"Stable neighbors: {changes_per_hour:.1f} changes/hour"

        return {
            "has_changes": True,
            "stability": stability,
            "description": description,
            "changes_per_hour": changes_per_hour,
            "total_changes": sum(neighbor_changes),
            "max_changes_in_sample": max(neighbor_changes)
        }

    def _check_state_abnormal(
        self,
        crc_trend: Dict,
        flap_frequency: Dict,
        neighbor_stability: Dict,
        thresholds: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        检查是否为状态异常

        Args:
            crc_trend: CRC趋势分析结果
            flap_frequency: Flap频率分析结果
            neighbor_stability: 邻居稳定性分析结果
            thresholds: 阈值配置

        Returns:
            (是否异常, 异常类型)
        """
        # CRC持续增长
        if crc_trend.get("has_crc_errors") and crc_trend.get("trend") == "increasing":
            if crc_trend.get("avg_crc", 0) > thresholds["crc_error_threshold"]:
                return True, "CRC_INCREASING"

        # 高频flap
        if flap_frequency.get("has_flaps") and flap_frequency.get("frequency") in ["medium", "high"]:
            if flap_frequency.get("flaps_per_hour", 0) > thresholds["flap_threshold"]:
                return True, "HIGH_FLAP_FREQUENCY"

        # 邻居不稳定
        if neighbor_stability.get("has_changes") and neighbor_stability.get("stability") in ["unstable", "fluctuating"]:
            if neighbor_stability.get("changes_per_hour", 0) > thresholds["neighbor_change_threshold"]:
                return True, "NEIGHBOR_UNSTABLE"

        return False, None


# 全局状态聚合器实例
state_aggregator = StateAggregator()
