"""
告警服务
基于研判结果生成和推送告警
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from database import SessionLocal
from models.automation import LogAnalysisResult, Site, AlertEvent

logger = logging.getLogger(__name__)


class AlertService:
    """告警服务"""

    def __init__(self):
        self.alert_cache = {}  # 用于告警去重

    def generate_alert_from_analysis(self, analysis_result: LogAnalysisResult) -> Dict:
        """
        从分析结果生成告警

        Args:
            analysis_result: 分析结果

        Returns:
            告警字典
        """
        # 生成告警唯一标识（用于去重）
        alert_key = self._generate_alert_key(analysis_result)

        # 检查是否需要去重
        if self._should_deduplicate(alert_key):
            logger.info(f"Alert deduplicated: {alert_key}")
            return None

        # 构建告警
        alert = {
            "alert_id": f"alert_{datetime.now().strftime('%Y%m%d%H%M%S')}_{analysis_result.id}",
            "alert_key": alert_key,
            "alert_type": "DIAGNOSIS_ALERT",
            "site_id": analysis_result.site_id,
            "device_id": analysis_result.netbox_device_id,
            "severity": analysis_result.severity,
            "summary": analysis_result.summary,
            "details": analysis_result.evidence.get("diagnosis", {}).get("details", ""),
            "recommendations": analysis_result.recommendation,
            "confidence": analysis_result.evidence.get("diagnosis", {}).get("confidence", "unknown"),
            "problem_type": analysis_result.evidence.get("diagnosis", {}).get("problem_type", "unknown"),
            "risk_level": analysis_result.evidence.get("diagnosis", {}).get("risk_level", "unknown"),
            "created_at": datetime.now().isoformat(),
            "source": "AUTOMATED_DIAGNOSIS",
            "analysis_id": analysis_result.id
        }

        # 记录告警到缓存
        self._record_alert(alert_key, alert)

        logger.info(f"Generated alert: {alert['alert_id']}, severity: {alert['severity']}")

        return alert

    def _generate_alert_key(self, analysis_result: LogAnalysisResult) -> str:
        """
        生成告警唯一标识

        Args:
            analysis_result: 分析结果

        Returns:
            告警唯一标识
        """
        # 使用基地ID、设备ID、异常类型作为唯一标识
        key_parts = [
            str(analysis_result.site_id),
            str(analysis_result.netbox_device_id) if analysis_result.netbox_device_id else "unknown",
            analysis_result.evidence.get("diagnosis", {}).get("problem_type", "unknown")
        ]

        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _should_deduplicate(self, alert_key: str) -> bool:
        """
        检查是否需要去重

        Args:
            alert_key: 告警唯一标识

        Returns:
            是否需要去重
        """
        # 检查缓存中是否存在该告警
        if alert_key in self.alert_cache:
            cached_alert = self.alert_cache[alert_key]
            # 如果告警在30分钟内已发送，则去重
            alert_time = datetime.fromisoformat(cached_alert["created_at"])
            if datetime.now() - alert_time < timedelta(minutes=30):
                return True
            else:
                # 超过30分钟，移除缓存
                del self.alert_cache[alert_key]

        return False

    def _record_alert(self, alert_key: str, alert: Dict):
        """
        记录告警到缓存

        Args:
            alert_key: 告警唯一标识
            alert: 告警字典
        """
        self.alert_cache[alert_key] = alert

    def _upsert_alert_event(self, db: Session, alert: Dict) -> AlertEvent:
        record = db.query(AlertEvent).filter(AlertEvent.dedup_key == alert["alert_key"]).first()
        if not record:
            record = AlertEvent(
                source=alert.get("source", "AUTOMATED_DIAGNOSIS"),
                external_event_id=str(alert.get("analysis_id", "")) or None,
                dedup_key=alert["alert_key"],
            )
            db.add(record)

        record.site_id = alert.get("site_id")
        record.netbox_device_id = alert.get("device_id")
        record.host = None
        record.name = alert.get("summary") or "自动化诊断告警"
        record.severity = alert.get("severity") or "warning"
        record.severity_level = {"info": 1, "warning": 2, "critical": 4}.get(record.severity, 2)
        record.status = "open"
        record.acknowledged = False
        record.occurred_at = datetime.fromisoformat(alert["created_at"])
        record.last_seen_at = datetime.now()
        record.payload = alert
        return record

    async def send_dingtalk_alert(self, alert: Dict, webhook_url: Optional[str] = None):
        """
        发送钉钉告警

        Args:
            alert: 告警字典
            webhook_url: 钉钉webhook URL（可选）
        """
        if not webhook_url:
            logger.warning("Dingtalk webhook URL not configured, skipping alert")
            return

        try:
            # 构建钉钉消息
            message = self._build_dingtalk_message(alert)

            # 发送HTTP请求
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(webhook_url, json=message)
                response.raise_for_status()

            logger.info(f"Successfully sent Dingtalk alert: {alert['alert_id']}")

        except Exception as e:
            logger.error(f"Failed to send Dingtalk alert: {e}", exc_info=True)

    def _build_dingtalk_message(self, alert: Dict) -> Dict:
        """
        构建钉钉消息

        Args:
            alert: 告警字典

        Returns:
            钉钉消息字典
        """
        # 根据严重级别选择颜色
        severity_colors = {
            "info": "#0099FF",
            "warning": "#FF9900",
            "critical": "#FF0000"
        }
        color = severity_colors.get(alert["severity"], "#0099FF")

        # 构建消息内容
        title = f"【{alert['severity'].upper()}】{alert['summary']}"

        content = f"""## {title}

**告警类型**: 研判型告警
**问题类型**: {alert['problem_type']}
**置信度**: {alert['confidence']}
**风险等级**: {alert['risk_level']}

### 问题详情
{alert['details']}

### 处理建议
{alert['recommendations']}

---
*告警时间: {alert['created_at']}*
*告警ID: {alert['alert_id']}*
"""

        # 构建钉钉消息格式
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }

        return message

    async def process_new_analysis_results(self, site_id: Optional[int] = None):
        """
        处理新的分析结果，生成告警

        Args:
            site_id: 基地ID（可选）
        """
        db = SessionLocal()

        try:
            # 查询需要处理的分析结果
            query = db.query(LogAnalysisResult).filter(
                LogAnalysisResult.status == "completed",
                LogAnalysisResult.severity.in_(["warning", "critical"])
            )

            if site_id:
                query = query.filter(LogAnalysisResult.site_id == site_id)

            # 按时间排序，获取最近的结果
            results = query.order_by(LogAnalysisResult.created_at.desc()).limit(10).all()

            logger.info(f"Found {len(results)} analysis results to process for alerts")

            # 逐个处理
            for result in results:
                # 生成告警
                alert = self.generate_alert_from_analysis(result)

                if alert:
                    self._upsert_alert_event(db, alert)
                    # 发送钉钉告警（需要配置webhook）
                    # webhook_url = "YOUR_DINGTALK_WEBHOOK_URL"
                    # await self.send_dingtalk_alert(alert, webhook_url)
                    logger.info(f"Alert generated (not sent): {alert['alert_id']}")

            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing analysis results for alerts: {e}", exc_info=True)
        finally:
            db.close()


# 全局告警服务实例
alert_service = AlertService()
