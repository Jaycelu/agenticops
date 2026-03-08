"""
Baseline计算服务
计算日志模式的baseline统计信息，用于异常检测
"""
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import SessionLocal

logger = logging.getLogger(__name__)


class BaselineCalculator:
    """Baseline计算器"""
    
    @classmethod
    def calculate_7d_baseline(
        cls,
        site_id: int,
        netbox_device_id: int,
        log_fingerprint: str,
        db: Optional[Session] = None
    ) -> Dict:
        """
        计算7天baseline统计信息

        Args:
            site_id: 基地ID
            netbox_device_id: NetBox设备ID
            log_fingerprint: 日志指纹
            db: 数据库会话（可选）

        Returns:
            baseline统计信息字典
        """
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            # 查询过去7天的采样数据，从raw_data JSON中提取fingerprint和log_count
            sql = text("""
                SELECT
                    site_id,
                    netbox_device_id,
                    raw_data->>'log_fingerprint' AS log_fingerprint,
                    jsonb_array_length(raw_data::jsonb->'log_messages') AS log_count,
                    sampled_at
                FROM log_sample
                WHERE
                    site_id = :site_id
                    AND (netbox_device_id = :netbox_device_id OR :netbox_device_id IS NULL)
                    AND raw_data->>'log_fingerprint' = :log_fingerprint
                    AND sampled_at >= NOW() - INTERVAL '7 days'
                ORDER BY sampled_at DESC
            """)

            results = db.execute(sql, {
                'site_id': site_id,
                'netbox_device_id': netbox_device_id,
                'log_fingerprint': log_fingerprint
            }).fetchall()
            
            if results:
                # 计算统计信息
                log_counts = [row[2] for row in results if row[2] is not None]
                if log_counts:
                    baseline_avg_5m = sum(log_counts) / len(log_counts)
                    sorted_counts = sorted(log_counts)
                    p95_index = int(len(sorted_counts) * 0.95)
                    baseline_p95_5m = sorted_counts[p95_index] if p95_index < len(sorted_counts) else sorted_counts[-1]
                else:
                    baseline_avg_5m = None
                    baseline_p95_5m = None
                
                return {
                    'baseline_avg_5m': baseline_avg_5m,
                    'baseline_p95_5m': baseline_p95_5m,
                    'baseline_count_7d': len(results)
                }
            else:
                # 没有历史数据，返回默认值
                return {
                    'baseline_avg_5m': None,
                    'baseline_p95_5m': None,
                    'baseline_count_7d': 0
                }
                
        except Exception as e:
            logger.error(f"Error calculating baseline: {e}", exc_info=True)
            return {
                'baseline_avg_5m': None,
                'baseline_p95_5m': None,
                'baseline_count_7d': 0
            }
        finally:
            if should_close:
                db.close()
    
    @classmethod
    def calculate_deviation_ratio(
        cls,
        current_count: int,
        baseline_avg: Optional[float]
    ) -> Optional[float]:
        """
        计算偏离比率
        
        Args:
            current_count: 当前窗口的日志数量
            baseline_avg: baseline平均值
        
        Returns:
            偏离比率（current_count / baseline_avg）
        """
        if baseline_avg is None or baseline_avg == 0:
            return None
        return round(current_count / baseline_avg, 2)
    
    @classmethod
    def is_raw_anomaly(
        cls,
        log_count: int,
        baseline_avg_5m: Optional[float],
        baseline_p95_5m: Optional[float],
        baseline_count_7d: int
    ) -> bool:
        """
        判断是否为Raw Anomaly（行为偏离正常基线）
        
        判定条件（满足任意一个即为Raw Anomaly）：
        1. log_count >= baseline_p95_5m
        2. deviation_ratio >= 3
        3. baseline_count_7d < 5 且 log_count >= 3（新模式）
        
        Args:
            log_count: 当前窗口的日志数量
            baseline_avg_5m: baseline平均值
            baseline_p95_5m: baseline P95值
            baseline_count_7d: 7天出现次数
        
        Returns:
            是否为Raw Anomaly
        """
        # 条件1：超过P95阈值
        if baseline_p95_5m is not None and log_count >= baseline_p95_5m:
            return True
        
        # 条件2：偏离比率 >= 3
        deviation_ratio = cls.calculate_deviation_ratio(log_count, baseline_avg_5m)
        if deviation_ratio is not None and deviation_ratio >= 3:
            return True
        
        # 条件3：新模式（历史出现次数少，但当前出现频繁）
        if baseline_count_7d < 5 and log_count >= 3:
            return True
        
        return False


# 全局baseline计算器实例
baseline_calculator = BaselineCalculator()