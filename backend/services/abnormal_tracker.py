"""
异常跟踪服务
基于数据库持久化设备异常状态，实现累积、去重和冷却机制
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from models.automation import AbnormalTrackerState
from database import SessionLocal

logger = logging.getLogger(__name__)


class AbnormalTracker:
    """异常跟踪器（DB持久化）"""

    def __init__(self):
        from config.site_config import DEFAULT_SAMPLING_CONFIG

        tracker_config = DEFAULT_SAMPLING_CONFIG.get("abnormal_tracker", {})
        self.accumulation_threshold = tracker_config.get("accumulation_threshold", 3)
        self.dedup_window_minutes = tracker_config.get("dedup_window_minutes", 30)
        self.cooldown_minutes = tracker_config.get("cooldown_minutes", 60)

    def _get_or_create_state(
        self,
        db: Session,
        device_ip: str,
        abnormal_type: str,
        site_id: Optional[int] = None
    ) -> AbnormalTrackerState:
        state = db.query(AbnormalTrackerState).filter(
            AbnormalTrackerState.site_id == site_id,
            AbnormalTrackerState.device_ip == device_ip,
            AbnormalTrackerState.abnormal_type == abnormal_type
        ).first()

        if state:
            return state

        state = AbnormalTrackerState(
            site_id=site_id,
            device_ip=device_ip,
            abnormal_type=abnormal_type,
            count=0
        )
        db.add(state)
        db.flush()
        return state

    def should_trigger_diagnosis(
        self,
        device_ip: str,
        abnormal_type: str,
        db: Session,
        site_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        now = datetime.now()
        state = self._get_or_create_state(db, device_ip, abnormal_type, site_id)

        if state.last_trigger_time:
            cooldown_end = state.last_trigger_time + timedelta(minutes=self.cooldown_minutes)
            if now < cooldown_end:
                remaining_minutes = (cooldown_end - now).total_seconds() / 60
                return False, f"冷却中，还需等待 {remaining_minutes:.1f} 分钟"

        if state.last_trigger_time:
            dedup_end = state.last_trigger_time + timedelta(minutes=self.dedup_window_minutes)
            if now < dedup_end:
                return False, f"去重时间窗口内，{self.dedup_window_minutes} 分钟内已触发过"

        state.count = (state.count or 0) + 1
        state.last_abnormal_time = now

        if state.first_abnormal_time is None:
            state.first_abnormal_time = now

        if state.count >= self.accumulation_threshold:
            state.count = 0
            state.last_trigger_time = now
            db.commit()
            return True, f"达到累积阈值 {self.accumulation_threshold} 次，触发研判"

        db.commit()
        return False, f"累积次数不足 {state.count}/{self.accumulation_threshold}"

    def calculate_severity_based_on_persistence(
        self,
        device_ip: str,
        abnormal_type: str,
        base_severity: str,
        site_id: Optional[int] = None
    ) -> str:
        severity_levels = ["low", "medium", "high", "critical"]
        if base_severity not in severity_levels:
            return "medium"

        db = SessionLocal()
        try:
            state = db.query(AbnormalTrackerState).filter(
                AbnormalTrackerState.site_id == site_id,
                AbnormalTrackerState.device_ip == device_ip,
                AbnormalTrackerState.abnormal_type == abnormal_type
            ).first()

            if not state or state.first_abnormal_time is None:
                return base_severity

            now = datetime.now()
            duration_minutes = (now - state.first_abnormal_time).total_seconds() / 60
            current_index = severity_levels.index(base_severity)

            if duration_minutes < 30:
                return base_severity
            if duration_minutes < 60:
                return severity_levels[min(current_index + 1, len(severity_levels) - 1)]
            if duration_minutes < 120:
                return severity_levels[min(current_index + 2, len(severity_levels) - 1)]
            return "critical"
        finally:
            db.close()

    def reset_device_abnormal(
        self,
        device_ip: str,
        abnormal_type: Optional[str] = None,
        site_id: Optional[int] = None
    ):
        db = SessionLocal()
        try:
            query = db.query(AbnormalTrackerState).filter(
                AbnormalTrackerState.site_id == site_id,
                AbnormalTrackerState.device_ip == device_ip
            )
            if abnormal_type:
                query = query.filter(AbnormalTrackerState.abnormal_type == abnormal_type)

            states = query.all()
            for state in states:
                state.count = 0
                state.first_abnormal_time = None
                state.last_trigger_time = None
                state.last_abnormal_time = None
            db.commit()
        finally:
            db.close()

    def get_device_abnormal_status(
        self,
        device_ip: str,
        abnormal_type: Optional[str] = None,
        site_id: Optional[int] = None
    ) -> Dict:
        db = SessionLocal()
        try:
            query = db.query(AbnormalTrackerState).filter(
                AbnormalTrackerState.site_id == site_id,
                AbnormalTrackerState.device_ip == device_ip
            )
            if abnormal_type:
                query = query.filter(AbnormalTrackerState.abnormal_type == abnormal_type)
                state = query.first()
                if not state:
                    return {}
                return {
                    "count": state.count,
                    "first_abnormal_time": state.first_abnormal_time.isoformat() if state.first_abnormal_time else None,
                    "last_trigger_time": state.last_trigger_time.isoformat() if state.last_trigger_time else None,
                    "last_abnormal_time": state.last_abnormal_time.isoformat() if state.last_abnormal_time else None
                }

            states = query.all()
            return {
                state.abnormal_type: {
                    "count": state.count,
                    "first_abnormal_time": state.first_abnormal_time.isoformat() if state.first_abnormal_time else None,
                    "last_trigger_time": state.last_trigger_time.isoformat() if state.last_trigger_time else None,
                    "last_abnormal_time": state.last_abnormal_time.isoformat() if state.last_abnormal_time else None
                }
                for state in states
            }
        finally:
            db.close()

    def cleanup_old_states(self):
        now = datetime.now()
        cleanup_threshold = now - timedelta(hours=24)

        db = SessionLocal()
        try:
            stale_states = db.query(AbnormalTrackerState).filter(
                AbnormalTrackerState.last_abnormal_time.isnot(None),
                AbnormalTrackerState.last_abnormal_time < cleanup_threshold
            ).all()
            for state in stale_states:
                db.delete(state)
            db.commit()
            if stale_states:
                logger.info(f"Cleaned up {len(stale_states)} abnormal tracker states")
        finally:
            db.close()


abnormal_tracker = AbnormalTracker()
