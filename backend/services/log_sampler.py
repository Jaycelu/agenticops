"""
日志采样服务
定期从ELK采样日志数据，写入log_sample表
"""
import asyncio
import logging
import re
from copy import deepcopy
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import SessionLocal
from models.automation import Site, LogSample, RawAnomaly
from mcp.elk_mcp import ELKMCP
from config.site_config import get_site_config, get_log_collection_policy
from services.fingerprint_generator import fingerprint_generator
from services.baseline_calculator import baseline_calculator
from services.site_automation_service import site_automation_service

logger = logging.getLogger(__name__)


RISK_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class LogSampler:
    """日志采样器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.elk_mcp = ELKMCP()
        self.is_running = False
        self._event_loop = None

    async def start(self):
        """启动采样服务"""
        try:
            # 重置状态，确保每次启动都能正确添加任务
            if self.is_running:
                logger.info("Log sampler is already running, stopping first...")
                await self.stop()

            logger.info("Starting log sampler...")
        except Exception as e:
            logger.error(f"Failed to start log sampler: {e}", exc_info=True)
            raise

        # 获取当前event loop
        self._event_loop = asyncio.get_event_loop()
        logger.debug(f"Using event loop: {self._event_loop}")

        # 获取所有启用的基地配置
        from config.site_config import get_all_sites
        site_codes = get_all_sites()

        logger.info(f"Found {len(site_codes)} sites: {site_codes}")

        for site_code in site_codes:
            logger.info(f"Processing site: {site_code}")
            db = SessionLocal()
            try:
                if not site_automation_service.is_site_enabled(db, site_code=site_code):
                    logger.info(f"Skip scheduler registration for disabled site: {site_code}")
                    continue
            finally:
                db.close()
            config = get_site_config(site_code)
            if config:
                logger.info(f"Config found for {site_code}")
                sampling_config = config.get("sampling", {})
                interval_minutes = sampling_config.get("sampling_interval_minutes", 5)

                # 添加定时任务
                self.scheduler.add_job(
                    self.sample_site_logs,
                    'interval',
                    minutes=interval_minutes,
                    args=[site_code],
                    id=f"sample_{site_code}",
                    replace_existing=True
                )
                logger.info(f"Added sampling job for {site_code} with interval {interval_minutes} minutes")
                # 服务启动后立即采样一次，避免首轮要等待一个interval
                asyncio.create_task(self.sample_site_logs(site_code))

        self.scheduler.start()
        self.is_running = True
        logger.debug(
            f"Scheduler running={self.scheduler.running}, jobs={len(self.scheduler.get_jobs())}"
        )
        logger.info("Log sampler started successfully")

    async def stop(self):
        """停止采样服务"""
        if not self.is_running:
            return

        logger.info("Stopping log sampler...")
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Log sampler stopped")

    async def refresh_jobs(self):
        """根据最新基地开关刷新采样任务"""
        if self.is_running:
            await self.stop()
        await self.start()

    async def sample_site_logs(self, site_code: str):
        """
        采样指定基地的日志

        Args:
            site_code: 基地代码（大写，如DEYANG）
        """
        logger.info(f"Starting log sampling for {site_code}")
        check_db = SessionLocal()
        try:
            if not site_automation_service.is_site_enabled(check_db, site_code=site_code):
                logger.info(f"Automation disabled for {site_code}, skip sampling")
                return
        finally:
            check_db.close()

        try:
            # 获取基地配置
            site_config = get_site_config(site_code)
            if not site_config:
                logger.error(f"Site config not found for {site_code}")
                return

            # 获取采样配置
            sampling_config = site_config.get("sampling", {})
            time_window_minutes = sampling_config.get("time_window_minutes", 5)
            collection_policy = get_log_collection_policy(site_code) or {}

            # 计算时间窗口
            time_window_end = datetime.now()
            time_window_start = time_window_end - timedelta(minutes=time_window_minutes)

            # 转换时间范围为ELK格式
            time_range = f"-{time_window_minutes}m,now"

            # 转换为小写以匹配ELKMCP的base_configs
            base_name = site_code.lower()

            # 直接使用ELKMCP的query_logs_by_base方法，复用日志模块的筛选条件
            elk_result = await self.elk_mcp.execute({
                "action": "query_logs_by_base",
                "base_name": base_name,
                "time_range": time_range,
                "limit": 1000
            })

            if not elk_result.success:
                logger.error(f"ELK query failed for {site_code}: {elk_result.error}")
                return

            logs = elk_result.data.get("logs", [])
            logger.info(f"Retrieved {len(logs)} logs from ELK for {site_code}")

            # 按设备分组统计日志
            device_stats = self._aggregate_logs_by_device(logs, collection_policy)

            # 为本轮采样生成批次ID，便于前后端一致性核对
            batch_id = f"{site_code}_{time_window_end.strftime('%Y%m%d%H%M%S')}"

            # 写入数据库
            await self._write_samples_to_db(
                site_code=site_code,
                device_stats=device_stats,
                time_window_start=time_window_start,
                time_window_end=time_window_end,
                collection_policy=collection_policy,
                batch_id=batch_id
            )

            logger.info(f"Completed log sampling for {site_code}")

        except Exception as e:
            logger.error(f"Error sampling logs for {site_code}: {e}", exc_info=True)

    def _aggregate_logs_by_device(self, logs: List[Dict], collection_policy: Optional[Dict] = None) -> Dict[str, Dict]:
        """
        按设备聚合日志统计

        Args:
            logs: 日志列表

        Returns:
            设备统计字典 {device_ip: stats}
        """
        collection_policy = collection_policy or {}
        urgent_levels = set(collection_policy.get("urgent_levels", []))
        urgent_keywords = [k.lower() for k in collection_policy.get("urgent_keywords", [])]
        dedup_seconds = int(collection_policy.get("message_dedup_seconds", 120))

        device_stats: Dict[str, Dict[str, Any]] = {}
        dedup_index: Dict[str, Dict[str, datetime]] = defaultdict(dict)

        for log in logs:
            device_ip = log.get("device_ip", "Unknown")
            message = log.get("message", "")
            level = str(log.get("level", "unknown"))
            ts_str = log.get("timestamp")
            event_time = self._safe_parse_time(ts_str)

            if device_ip not in device_stats:
                device_stats[device_ip] = {
                    "error_count": 0,
                    "crc_error_count": 0,
                    "flap_count": 0,
                    "neighbor_change_count": 0,
                    "interface_state_change_count": 0,
                    "critical_event_count": 0,
                    "hardware_alarm_count": 0,
                    "auth_failure_count": 0,
                    "routing_instability_count": 0,
                    "other_error_count": 0,  # 其他错误日志数量
                    "log_messages": [],
                    "critical_messages": [],
                    "other_error_fingerprints": set()  # 其他错误日志的指纹集合
                }

            stats = device_stats[device_ip]
            normalized_message = message.lower()

            # 同设备同类消息在短时间去重，降低重复刷屏影响
            dedup_key = fingerprint_generator.generate_fingerprint(message) or normalized_message[:200]
            last_seen = dedup_index[device_ip].get(dedup_key)
            if last_seen and event_time and (event_time - last_seen).total_seconds() <= dedup_seconds:
                continue
            if event_time:
                dedup_index[device_ip][dedup_key] = event_time

            # 统计错误数量
            if level in ["Error", "Critical", "Emergencies", "Alert"]:
                stats["error_count"] += 1

            # 统计CRC错误
            if "CRC" in message.upper():
                stats["crc_error_count"] += 1

            # 统计接口flap
            if "flap" in message.lower():
                stats["flap_count"] += 1

            if self._is_interface_state_change(normalized_message):
                stats["interface_state_change_count"] += 1

            # 统计邻居变化
            if "neighbor" in normalized_message and ("change" in normalized_message or "down" in normalized_message):
                stats["neighbor_change_count"] += 1

            if self._is_hardware_alarm(normalized_message):
                stats["hardware_alarm_count"] += 1

            if self._is_auth_failure(normalized_message):
                stats["auth_failure_count"] += 1

            if self._is_routing_instability(normalized_message):
                stats["routing_instability_count"] += 1

            if level in urgent_levels or any(k in normalized_message for k in urgent_keywords):
                stats["critical_event_count"] += 1
                if len(stats["critical_messages"]) < 50:
                    stats["critical_messages"].append(message)

            # 统计其他错误日志（不属于已知四类的错误日志）
            if level in ["Error", "Critical", "Emergencies", "Alert"]:
                # 检查是否属于已知的四类
                is_known_type = (
                    "CRC" in message.upper() or
                    "flap" in normalized_message or
                    ("neighbor" in normalized_message and ("change" in normalized_message or "down" in normalized_message)) or
                    self._is_interface_state_change(normalized_message) or
                    self._is_hardware_alarm(normalized_message) or
                    self._is_auth_failure(normalized_message)
                )

                if not is_known_type:
                    stats["other_error_count"] += 1
                    # 生成指纹
                    fingerprint = fingerprint_generator.generate_fingerprint(message)
                    if fingerprint:
                        stats["other_error_fingerprints"].add(fingerprint)

            # 保存日志消息（最多保存200条）
            if len(stats["log_messages"]) < 200:
                stats["log_messages"].append(message)

        # 转换fingerprint集合为列表
        for device_ip, stats in device_stats.items():
            if "other_error_fingerprints" in stats:
                stats["other_error_fingerprints"] = list(stats["other_error_fingerprints"])

        return device_stats

    def _safe_parse_time(self, time_str: Optional[str]) -> Optional[datetime]:
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def _is_interface_state_change(self, msg: str) -> bool:
        patterns = [
            r"interface .* (up|down)",
            r"line protocol .* (up|down)",
            r"link(up|down)",
            r"changed state to (up|down)",
            r"port .* (up|down)",
        ]
        return any(re.search(p, msg) for p in patterns)

    def _is_hardware_alarm(self, msg: str) -> bool:
        keywords = [
            "fan fail", "power fail", "temperature", "overheat", "sfp fault",
            "transceiver fault", "optical module fault", "hardware fault", "los"
        ]
        return any(k in msg for k in keywords)

    def _is_auth_failure(self, msg: str) -> bool:
        keywords = [
            "authentication failed", "login failed", "bad password", "invalid user",
            "failed password", "ssh auth fail"
        ]
        return any(k in msg for k in keywords)

    def _is_routing_instability(self, msg: str) -> bool:
        routing_tokens = ["bgp", "ospf", "isis", "eigrp", "route"]
        unstable_tokens = ["down", "reset", "flap", "change", "timeout"]
        return any(r in msg for r in routing_tokens) and any(u in msg for u in unstable_tokens)

    async def _write_samples_to_db(
        self,
        site_code: str,
        device_stats: Dict[str, Dict],
        time_window_start: datetime,
        time_window_end: datetime,
        collection_policy: Optional[Dict] = None,
        batch_id: Optional[str] = None
    ):
        """
        将采样数据写入数据库
        只记录有异常的设备

        Args:
            site_code: 基地代码
            device_stats: 设备统计字典
            time_window_start: 时间窗口开始
            time_window_end: 时间窗口结束
        """
        db = SessionLocal()

        try:
            # 获取基地ID
            site = db.query(Site).filter(Site.site_code == site_code).first()
            if not site:
                # 兜底：若site表未初始化，自动创建，避免采样任务完全丢失
                site_config = get_site_config(site_code) or {}
                site = Site(
                    site_code=site_code,
                    site_name=site_config.get("site_name", site_code),
                    description=site_config.get("description", f"{site_code} auto-created by sampler")
                )
                db.add(site)
                db.flush()
                logger.warning(f"Site not found in DB, auto-created: {site_code}")

            site_id = site.id

            # 为每个有日志的设备都创建采样记录；异常仅作为标记字段
            abnormal_devices_count = 0
            total_samples_count = 0
            triggered_abnormal_sample_ids: List[int] = []
            for device_ip, stats in device_stats.items():
                policy_decision = self._evaluate_collection_policy(
                    db=db,
                    site_id=site_id,
                    site_code=site_code,
                    device_ip=device_ip,
                    stats=stats,
                    collection_policy=collection_policy or {}
                )
                pattern_summary = self._summarize_log_patterns(stats)
                signal_summary = self._build_signal_summary(stats, policy_decision, pattern_summary)

                is_abnormal = signal_summary["signal_score"] > 0
                if is_abnormal:
                    abnormal_devices_count += 1

                # 通过NetBox API获取设备ID
                netbox_device_id = await self._get_device_id_from_netbox(device_ip, site_code)

                # 生成指纹和日志计数
                log_fingerprint = None
                log_count = len(stats["log_messages"])

                if log_count > 0:
                    # 生成指纹（使用第一条日志）
                    log_fingerprint = fingerprint_generator.generate_fingerprint(stats["log_messages"][0])

                # 创建采样记录
                log_sample = LogSample(
                    site_id=site_id,
                    netbox_device_id=netbox_device_id,
                    error_count=stats["error_count"],
                    crc_error_count=stats["crc_error_count"],
                    flap_count=stats["flap_count"],
                    neighbor_change_count=stats["neighbor_change_count"],
                    sampled_at=datetime.now(),
                    time_window_start=time_window_start,
                    time_window_end=time_window_end,
                    is_abnormal=is_abnormal,
                    raw_data={
                        "device_ip": device_ip,
                        "batch_id": batch_id,
                        "log_messages": stats["log_messages"],
                        "other_error_count": stats.get("other_error_count", 0),
                        "other_error_fingerprints": stats.get("other_error_fingerprints", []),
                        "collection_policy_decision": policy_decision,
                        "signal_summary": signal_summary,
                        "pattern_summary": pattern_summary,
                        "trigger_reason": policy_decision.get("reason"),
                        "case": None,
                    }
                )

                db.add(log_sample)
                db.flush()  # 确保log_sample有ID
                total_samples_count += 1

                if signal_summary["should_create_case"]:
                    triggered_abnormal_sample_ids.append(log_sample.id)

                if is_abnormal and log_fingerprint and log_count > 0:
                    # 如果没有设备ID，使用-1作为占位符
                    device_id_for_baseline = netbox_device_id if netbox_device_id else -1
                    await self._check_and_create_raw_anomaly(
                        db, site_id, device_id_for_baseline, device_ip, log_fingerprint,
                        log_count, stats["log_messages"],
                        time_window_start, time_window_end
                    )

                # 注意：采样阶段不直接创建任务，统一走编排器详细研判链路，
                # 避免出现“有任务但无证据”的旁路任务。

            db.commit()
            logger.info(
                "Found %s devices, wrote %s samples (%s abnormal) to database for %s",
                len(device_stats), total_samples_count, abnormal_devices_count, site_code
            )

            # 触发研判流程（异步）
            if triggered_abnormal_sample_ids:
                asyncio.create_task(
                    self._trigger_diagnosis_for_abnormal_samples(
                        site_id=site_id,
                        sample_ids=triggered_abnormal_sample_ids
                    )
                )

        except Exception as e:
            db.rollback()
            logger.error(f"Error writing samples to database: {e}", exc_info=True)
            raise
        finally:
            db.close()

    async def _trigger_diagnosis_for_abnormal_samples(
        self,
        site_id: int,
        sample_ids: Optional[List[int]] = None
    ):
        """
        触发异常采样的研判流程

        Args:
            site_id: 基地ID
            sample_ids: 当前采样周期写入的异常采样ID列表
        """
        try:
            logger.debug(f"Trigger diagnosis called for site_id={site_id}")

            # 获取基地信息
            from database import SessionLocal
            db_new = SessionLocal()
            try:
                from models.automation import Site, LogSample
                site = db_new.query(Site).filter(Site.id == site_id).first()

                if not site:
                    logger.error(f"Site not found: {site_id}")
                    return

                query = db_new.query(LogSample).filter(
                    LogSample.site_id == site.id,
                    LogSample.is_abnormal == True
                )
                if sample_ids:
                    query = query.filter(LogSample.id.in_(sample_ids))
                else:
                    from datetime import datetime, timedelta
                    time_threshold = datetime.now() - timedelta(minutes=30)
                    query = query.filter(LogSample.created_at >= time_threshold)

                abnormal_samples = query.order_by(LogSample.created_at.desc()).all()

                logger.info(f"Found {len(abnormal_samples)} abnormal samples for site {site.site_code}")

                triggered_count = 0
                for sample in abnormal_samples:
                    try:
                        result = await self._create_case_for_sample_with_db(db_new, site, sample, rerun_pipeline=False)
                        if result.get("case_id"):
                            triggered_count += 1
                    except Exception as e:
                        logger.error(
                            f"Error creating case for sample {sample.id}: {e}",
                            exc_info=True
                        )

                if triggered_count > 0:
                    logger.info(f"Triggered {triggered_count} case pipelines for {site.site_code}")
                else:
                    logger.info(f"No case pipelines triggered for {site.site_code}")

            except Exception as e:
                logger.error(f"Error triggering diagnosis: {e}", exc_info=True)

            finally:
                db_new.close()

        except Exception as e:
            logger.error(f"Error in _trigger_diagnosis_for_abnormal_samples: {e}", exc_info=True)

    def _evaluate_collection_policy(
        self,
        db: Session,
        site_id: int,
        site_code: str,
        device_ip: str,
        stats: Dict[str, Any],
        collection_policy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估日志采集策略。
        优先级：
        1) 严重事件实时触发；
        2) 普通事件按周期累计触发；
        3) 其余仅记录为观测信号，由多 Agent 在 case 中集中判断。
        """
        immediate_cfg = collection_policy.get("immediate_trigger", {})
        periodic_cfg = collection_policy.get("periodic_trigger", {})

        # 1) 严重事件实时触发
        immediate_checks = [
            ("critical_event_count", "critical_log_alert", "严重日志告警", "critical"),
            ("hardware_alarm_count", "hardware_issue", "硬件告警", "critical"),
            ("auth_failure_count", "security_auth_failure", "认证失败", "high"),
        ]
        for field, signal_key, signal_title, risk_level in immediate_checks:
            val = int(stats.get(field, 0) or 0)
            threshold = int(immediate_cfg.get(field, 0) or 0)
            if threshold > 0 and val >= threshold:
                return {
                    "should_trigger": True,
                    "reason": f"[immediate] {field} reached {val}/{threshold}",
                    "trigger_mode": "immediate",
                    "signal_key": signal_key,
                    "signal_title": signal_title,
                    "risk_level": risk_level,
                }

        # 2) 周期累计触发（例如接口up/down 30次/天）
        for field, cfg in periodic_cfg.items():
            val = int(stats.get(field, 0) or 0)
            if val <= 0:
                continue

            threshold = int(cfg.get("threshold", 0) or 0)
            window_minutes = int(cfg.get("window_minutes", 1440) or 1440)
            signal_key = cfg.get("signal_key") or cfg.get("abnormal_type", field).lower()
            if threshold <= 0:
                continue

            if val >= threshold:
                return {
                    "should_trigger": True,
                    "reason": f"[periodic:{field}] {val}/{threshold} within {window_minutes}m",
                    "trigger_mode": "periodic",
                    "signal_key": signal_key,
                    "signal_title": cfg.get("title", field),
                    "risk_level": cfg.get("risk_level", "medium"),
                }

        # 3) 仅记录观察信号，不在采样层做根因判断
        return {
            "should_trigger": False,
            "reason": "observed_signal_only",
            "trigger_mode": "observe",
            "signal_key": None,
            "signal_title": None,
            "risk_level": "low",
        }

    def _summarize_log_patterns(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        fingerprints: Dict[str, Dict[str, Any]] = {}
        for message in stats.get("log_messages", [])[:100]:
            fingerprint = fingerprint_generator.generate_fingerprint(message)
            bucket = fingerprints.setdefault(
                fingerprint,
                {"fingerprint": fingerprint, "count": 0, "example": message[:300]},
            )
            bucket["count"] += 1

        top_patterns = sorted(
            fingerprints.values(),
            key=lambda item: item["count"],
            reverse=True,
        )[:5]
        return {
            "message_count": len(stats.get("log_messages", [])),
            "critical_examples": stats.get("critical_messages", [])[:5],
            "top_patterns": top_patterns,
        }

    def _build_signal_summary(
        self,
        stats: Dict[str, Any],
        policy_decision: Dict[str, Any],
        pattern_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        signal_defs = [
            ("crc_error_count", "crc_errors", "CRC 错误", "high"),
            ("flap_count", "interface_flap", "接口震荡", "medium"),
            ("neighbor_change_count", "neighbor_change", "邻居变化", "medium"),
            ("interface_state_change_count", "interface_state_change", "接口状态变化", "medium"),
            ("routing_instability_count", "routing_instability", "路由抖动", "high"),
            ("hardware_alarm_count", "hardware_alarm", "硬件告警", "critical"),
            ("auth_failure_count", "auth_failure", "认证失败", "high"),
            ("critical_event_count", "critical_events", "严重日志", "critical"),
            ("other_error_count", "unknown_error_patterns", "未知错误模式", "medium"),
        ]

        signals: List[Dict[str, Any]] = []
        score = 0.0
        highest_risk = "low"
        for field, key, title, risk in signal_defs:
            count = int(stats.get(field, 0) or 0)
            if count <= 0:
                continue
            signals.append(
                {
                    "field": field,
                    "key": key,
                    "title": title,
                    "count": count,
                    "risk_level": risk,
                }
            )
            score += 1 + min(count / 20, 1.5)
            if RISK_ORDER[risk] > RISK_ORDER[highest_risk]:
                highest_risk = risk

        policy_risk = policy_decision.get("risk_level") or highest_risk
        if RISK_ORDER.get(policy_risk, 0) > RISK_ORDER[highest_risk]:
            highest_risk = policy_risk

        primary_signal = policy_decision.get("signal_key") or (signals[0]["key"] if signals else None)
        signal_title = policy_decision.get("signal_title") or (signals[0]["title"] if signals else "观测信号")
        should_create_case = bool(policy_decision.get("should_trigger")) or (
            primary_signal is not None and RISK_ORDER.get(highest_risk, 0) >= RISK_ORDER["high"]
        ) or score >= 3.0

        return {
            "primary_signal": primary_signal,
            "signal_title": signal_title,
            "risk_level": highest_risk,
            "signal_score": round(score, 2),
            "trigger_mode": policy_decision.get("trigger_mode", "observe"),
            "trigger_reason": policy_decision.get("reason"),
            "should_create_case": should_create_case,
            "signals": signals,
            "top_pattern": ((pattern_summary.get("top_patterns") or [{}])[0] if pattern_summary else {}),
        }

    async def create_case_for_sample(self, sample_id: int, rerun_pipeline: bool = False) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            sample = db.query(LogSample).filter(LogSample.id == sample_id).first()
            if not sample:
                raise ValueError(f"sample not found: {sample_id}")
            site = db.query(Site).filter(Site.id == sample.site_id).first()
            if not site:
                raise ValueError(f"site not found: {sample.site_id}")
            return await self._create_case_for_sample_with_db(db, site, sample, rerun_pipeline=rerun_pipeline)
        finally:
            db.close()

    async def _create_case_for_sample_with_db(
        self,
        db: Session,
        site: Site,
        sample: LogSample,
        *,
        rerun_pipeline: bool,
    ) -> Dict[str, Any]:
        from engines.case_orchestrator import case_orchestrator

        raw_data = deepcopy(sample.raw_data or {})
        existing_case = raw_data.get("case") or {}
        if existing_case.get("case_id") and existing_case.get("case_code") and not rerun_pipeline:
            return existing_case

        signal_summary = raw_data.get("signal_summary") or {}
        pattern_summary = raw_data.get("pattern_summary") or {}
        device_ip = raw_data.get("device_ip")
        top_pattern = ((pattern_summary.get("top_patterns") or [{}])[0] if pattern_summary else {})
        severity = signal_summary.get("risk_level") or "warning"
        title = f"[{site.site_code}] {device_ip or sample.netbox_device_id or 'device'} 日志信号"
        summary = (
            f"{signal_summary.get('signal_title') or '日志模式异常'}"
            f"，score={signal_summary.get('signal_score', 0)}"
            f"，messages={pattern_summary.get('message_count', 0)}"
        )
        window_minutes = 15
        if sample.time_window_start and sample.time_window_end:
            try:
                delta = sample.time_window_end - sample.time_window_start
                window_minutes = max(15, min(1440, int(delta.total_seconds() / 60)))
            except Exception:
                window_minutes = 15

        case = await case_orchestrator.intake_case(
            db,
            title=title,
            source_type="log_signal",
            source_system="ELK_SAMPLER",
            dedup_key=f"log-sample:{sample.id}",
            severity=severity,
            site_id=sample.site_id,
            netbox_device_id=sample.netbox_device_id,
            device_ip=device_ip,
            host=device_ip,
            summary=summary,
            occurred_at=sample.sampled_at,
            raw_payload={
                "sample_id": sample.id,
                "batch_id": raw_data.get("batch_id"),
                "stats": {
                    "error_count": sample.error_count,
                    "crc_error_count": sample.crc_error_count,
                    "flap_count": sample.flap_count,
                    "neighbor_change_count": sample.neighbor_change_count,
                },
                "log_messages": raw_data.get("log_messages", [])[:50],
            },
            normalized_payload={
                "signal_summary": signal_summary,
                "pattern_summary": pattern_summary,
                "top_pattern": top_pattern,
            },
            case_metadata={
                "source": "log_sampler",
                "sample_id": sample.id,
                "batch_id": raw_data.get("batch_id"),
                "site_code": site.site_code,
            },
        )
        if not existing_case.get("case_id") or rerun_pipeline:
            await case_orchestrator.run_case_pipeline(
                db,
                case_id=case.id,
                base_name=site.site_code.lower(),
                log_query=device_ip,
                time_range=f"-{max(window_minutes * 2, 15)}m,now",
                log_limit=max(200, min(1000, pattern_summary.get("message_count", 200) or 200)),
            )

        raw_data["case"] = {
            "case_id": case.id,
            "case_code": case.case_code,
            "created_at": datetime.now().isoformat(),
        }
        sample.raw_data = raw_data
        db.commit()
        return raw_data["case"]
    
    async def _get_device_id_from_netbox(self, device_ip: str, site_code: str) -> Optional[int]:
        """
        通过NetBox API获取设备ID

        Args:
            device_ip: 设备IP
            site_code: 基地代码

        Returns:
            设备ID，如果未找到则返回None
        """
        try:
            from mcp.netbox_mcp import NetBoxMCP
            netbox_mcp = NetBoxMCP()

            # 通过IP地址查询设备
            result = await netbox_mcp.execute({
                "action": "query_ips",
                "address": device_ip
            })

            if result.success and result.data.get("count", 0) > 0:
                ips = result.data.get("ips", [])
                for ip in ips:
                    if ip.get("assigned_object_type") == "dcim.device":
                        return ip.get("assigned_object_id")

            logger.warning(f"Device not found in NetBox for IP: {device_ip}")
            return None

        except Exception as e:
            logger.error(f"Error getting device ID from NetBox: {e}", exc_info=True)
            return None

    async def _run_rule_engine_diagnosis(
        self,
        db: Session,
        site_id: int,
        netbox_device_id: Optional[int],
        device_ip: str,
        device_stats: Dict[str, Any],
        log_sample: LogSample
    ):
        """
        运行规则引擎诊断

        Args:
            db: 数据库会话
            site_id: 基地ID
            netbox_device_id: NetBox设备ID
            device_ip: 设备IP
            device_stats: 设备统计数据
            log_sample: 日志采样对象
        """
        try:
            # 导入规则评估器和决策服务
            from services.rule_evaluator import rule_evaluator
            from services.llm_diagnosis import llm_diagnosis_service
            from services.decision_service import decision_service
            from services.schemas import DecisionResult, TaskTriggerEvent

            # 1. 运行规则引擎
            rule_results = rule_evaluator.evaluate_log_sample(
                site_id, device_ip, device_stats
            )

            # 2. 如果规则匹配，创建决策任务
            if rule_results:
                logger.info(f"Rule engine matched {len(rule_results)} rules for {device_ip}")

                for rule_result in rule_results:
                    # 转换规则结果为DecisionResult
                    diagnosis_result = rule_result["result"]
                    base_severity = diagnosis_result.get("severity", "medium")
                    diagnosis_result["severity"] = base_severity
                    diagnosis_result["risk_level"] = base_severity

                    decision_result = DecisionResult(
                        rule_id=rule_result["rule_id"],
                        rule_name=rule_result["rule_name"],
                        diagnosis=diagnosis_result,
                        context=device_stats
                    )

                    # 创建触发事件
                    trigger_event = TaskTriggerEvent(
                        event_type="log_sample",
                        source_id=log_sample.id,
                        source_type="LogSample",
                        data=device_stats
                    )

                    # 创建决策任务
                    await decision_service.create_decision_task(
                        site_id=site_id,
                        netbox_device_id=netbox_device_id,
                        device_ip=device_ip,
                        decision_result=decision_result,
                        trigger_event=trigger_event
                    )

            # 3. 如果没有规则匹配，使用LLM诊断
            else:
                logger.debug(f"No rules matched for {device_ip}, using LLM diagnosis")

                # 获取设备信息
                device_info = None
                if netbox_device_id:
                    try:
                        from mcp.netbox_mcp import NetBoxMCP
                        netbox_mcp = NetBoxMCP()
                        result = await netbox_mcp.execute({
                            "action": "get_device_by_id",
                            "device_id": netbox_device_id
                        })
                        if result.success and result.data:
                            device_info = result.data
                    except Exception as e:
                        logger.warning(f"Error getting device info from NetBox: {e}")

                # 调用LLM诊断
                llm_diagnosis = await llm_diagnosis_service.diagnose_log_sample(
                    site_id=site_id,
                    device_ip=device_ip,
                    device_stats=device_stats,
                    device_info=device_info
                )

                # 创建决策结果
                decision_result = DecisionResult(
                    rule_id=None,
                    rule_name="LLM Diagnosis",
                    diagnosis=llm_diagnosis,
                    context=device_stats
                )

                # 创建触发事件
                trigger_event = TaskTriggerEvent(
                    event_type="log_sample",
                    source_id=log_sample.id,
                    source_type="LogSample",
                    data=device_stats
                )

                # 创建决策任务
                await decision_service.create_decision_task(
                    site_id=site_id,
                    netbox_device_id=netbox_device_id,
                    device_ip=device_ip,
                    decision_result=decision_result,
                    trigger_event=trigger_event
                )

        except Exception as e:
            logger.error(f"Error running rule engine diagnosis: {e}", exc_info=True)

    async def _check_and_create_raw_anomaly(
        self,
        db: Session,
        site_id: int,
        netbox_device_id: int,
        device_ip: str,
        log_fingerprint: str,
        log_count: int,
        log_messages: List[str],
        time_window_start: datetime,
        time_window_end: datetime
    ):
        """
        检查并创建Raw Anomaly

        Args:
            db: 数据库会话
            site_id: 基地ID
            netbox_device_id: NetBox设备ID
            device_ip: 设备IP
            log_fingerprint: 日志指纹
            log_count: 日志数量
            log_messages: 日志消息列表
            time_window_start: 时间窗口开始
            time_window_end: 时间窗口结束
        """
        try:
            # 计算baseline
            baseline = baseline_calculator.calculate_7d_baseline(
                site_id, netbox_device_id, log_fingerprint, db
            )

            # 判断是否为Raw Anomaly
            is_anomaly = baseline_calculator.is_raw_anomaly(
                log_count,
                baseline['baseline_avg_5m'],
                baseline['baseline_p95_5m'],
                baseline['baseline_count_7d']
            )

            if is_anomaly:
                # 检查是否已存在相同的Raw Anomaly（去重）
                existing = db.query(RawAnomaly).filter(
                    RawAnomaly.site_id == site_id,
                    RawAnomaly.device_ip == device_ip,
                    RawAnomaly.log_fingerprint == log_fingerprint,
                    RawAnomaly.time_window_start == time_window_start
                ).first()

                if not existing:
                    # 创建新的Raw Anomaly
                    raw_anomaly = RawAnomaly(
                        site_id=site_id,
                        device_id=netbox_device_id,
                        device_ip=device_ip,
                        time_window_start=time_window_start,
                        time_window_end=time_window_end,
                        log_fingerprint=log_fingerprint,
                        log_samples={"messages": log_messages},
                        log_count=log_count,
                        baseline_avg_5m=baseline['baseline_avg_5m'],
                        baseline_p95_5m=baseline['baseline_p95_5m'],
                        baseline_count_7d=baseline['baseline_count_7d'],
                        deviation_ratio=baseline_calculator.calculate_deviation_ratio(
                            log_count, baseline['baseline_avg_5m']
                        ),
                        pre_class=None,
                        ai_class=None,
                        severity=None,
                        confidence=None,
                        status="NEW"
                    )

                    db.add(raw_anomaly)
                    db.commit()
                    logger.info(f"Created Raw Anomaly for {device_ip} with {log_count} logs")
                else:
                    # 更新last_seen_at
                    existing.last_seen_at = datetime.now()
                    db.commit()
                    logger.info(f"Updated existing Raw Anomaly for {device_ip}")
                    
        except Exception as e:
            logger.error(f"Error checking/creating Raw Anomaly: {e}", exc_info=True)
            db.rollback()


# 全局采样器实例
log_sampler = LogSampler()
