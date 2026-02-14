"""
日志采样服务
定期从ELK采样日志数据，写入log_sample表
"""
import asyncio
import logging
import re
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

logger = logging.getLogger(__name__)


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

    async def sample_site_logs(self, site_code: str):
        """
        采样指定基地的日志

        Args:
            site_code: 基地代码（大写，如DEYANG）
        """
        logger.info(f"Starting log sampling for {site_code}")

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

            # 写入数据库
            await self._write_samples_to_db(
                site_code=site_code,
                device_stats=device_stats,
                time_window_start=time_window_start,
                time_window_end=time_window_end,
                collection_policy=collection_policy
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
        collection_policy: Optional[Dict] = None
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

            # 导入异常类型管理服务
            from services.abnormal_type_service import abnormal_type_service

            # 为每个有日志的设备都创建采样记录；异常仅作为标记字段
            abnormal_devices_count = 0
            total_samples_count = 0
            for device_ip, stats in device_stats.items():
                policy_decision = self._evaluate_collection_policy(
                    db=db,
                    site_id=site_id,
                    site_code=site_code,
                    device_ip=device_ip,
                    stats=stats,
                    collection_policy=collection_policy or {}
                )

                # 使用异常类型管理服务进行判定
                matched_type = abnormal_type_service.match_abnormal_type(
                    db,
                    error_count=stats["error_count"],
                    crc_error_count=stats["crc_error_count"],
                    flap_count=stats["flap_count"],
                    neighbor_change_count=stats["neighbor_change_count"],
                    other_error_count=stats.get("other_error_count", 0),
                    other_error_fingerprints=stats.get("other_error_fingerprints", []),
                    interface_state_change_count=stats.get("interface_state_change_count", 0),
                    critical_event_count=stats.get("critical_event_count", 0),
                    hardware_alarm_count=stats.get("hardware_alarm_count", 0),
                )

                # 策略可覆盖异常类型（例如严重日志实时触发）
                # 仅在策略判定允许触发时使用覆盖类型
                if policy_decision.get("should_trigger") and policy_decision.get("matched_type_override"):
                    matched_type = policy_decision["matched_type_override"]

                # 如果仍未匹配到异常类型，补一个通用高错误率类型
                if not matched_type and policy_decision.get("trigger_mode") in {"immediate", "periodic"}:
                    matched_type = {
                        "type_code": "HIGH_ERROR_RATE",
                        "type_name": "高错误率",
                        "risk_level": "medium",
                        "enable_tracking": True,
                        "tracking_config": {}
                    }

                is_abnormal = matched_type is not None
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
                    abnormal_type=matched_type["type_code"] if matched_type else None,
                    raw_data={
                        "device_ip": device_ip,
                        "log_messages": stats["log_messages"],
                        "other_error_count": stats.get("other_error_count", 0),
                        "other_error_fingerprints": stats.get("other_error_fingerprints", []),
                        "matched_type": matched_type,
                        "collection_policy_decision": policy_decision
                    }
                )

                # 添加指纹和日志计数
                if log_fingerprint:
                    log_sample.log_fingerprint = log_fingerprint
                log_sample.log_count = log_count

                db.add(log_sample)
                db.flush()  # 确保log_sample有ID
                total_samples_count += 1

                # 更新异常类型的出现次数
                should_process_abnormal = is_abnormal and policy_decision.get("should_trigger", True)
                if should_process_abnormal:
                    abnormal_type_service.update_occurrence(db, matched_type["type_code"])

                # 如果不是已知异常，检查是否为Raw Anomaly
                if should_process_abnormal and matched_type["type_code"].startswith("UNKNOWN_") and log_fingerprint and log_count > 0:
                    # 如果没有设备ID，使用-1作为占位符
                    device_id_for_baseline = netbox_device_id if netbox_device_id else -1
                    await self._check_and_create_raw_anomaly(
                        db, site_id, device_id_for_baseline, device_ip, log_fingerprint,
                        log_count, stats["log_messages"],
                        time_window_start, time_window_end
                    )

                # 仅对异常采样调用规则引擎和后续自动化
                if should_process_abnormal:
                    await self._run_rule_engine_diagnosis(
                        db, site_id, netbox_device_id, device_ip, stats, log_sample
                    )

            db.commit()
            logger.info(
                "Found %s devices, wrote %s samples (%s abnormal) to database for %s",
                len(device_stats), total_samples_count, abnormal_devices_count, site_code
            )

            # 触发研判流程（异步）
            if abnormal_devices_count > 0:
                asyncio.create_task(self._trigger_diagnosis_for_abnormal_samples(db, site_id, device_stats, {}))

        except Exception as e:
            db.rollback()
            logger.error(f"Error writing samples to database: {e}", exc_info=True)
            raise
        finally:
            db.close()

    async def _trigger_diagnosis_for_abnormal_samples(
        self,
        db: Session,
        site_id: str,
        device_stats: Dict[str, Dict],
        thresholds: Dict
    ):
        """
        触发异常采样的研判流程

        Args:
            db: 数据库会话
            site_id: 基地代码或ID
            device_stats: 设备统计字典
            thresholds: 阈值配置
        """
        try:
            logger.debug(f"Trigger diagnosis called for site_id={site_id}")
            # 导入自动化编排器（避免循环导入）
            from services.automation_orchestrator import automation_orchestrator
            from services.abnormal_tracker import abnormal_tracker

            # 获取基地信息
            from database import SessionLocal
            db_new = SessionLocal()
            try:
                from models.automation import Site
                # 如果传入的是site_id（整数），直接使用
                # 如果传入的是site_code（字符串），需要查询获取site_id
                if isinstance(site_id, int):
                    site = db_new.query(Site).filter(Site.id == site_id).first()
                else:
                    site = db_new.query(Site).filter(Site.site_code == site_id).first()

                if not site:
                    logger.error(f"Site not found: {site_id}")
                    return

                actual_site_id = site.id

                # 查询刚刚创建的异常采样
                from datetime import datetime, timedelta
                time_threshold = datetime.now() - timedelta(minutes=10)

                from models.automation import LogSample
                abnormal_samples = db_new.query(LogSample).filter(
                    LogSample.site_id == actual_site_id,
                    LogSample.is_abnormal == True,
                    LogSample.created_at >= time_threshold
                ).order_by(LogSample.created_at.desc()).limit(5).all()

                logger.info(f"Found {len(abnormal_samples)} abnormal samples for site {site.site_code}")

                # 触发研判（使用异常跟踪器进行去重和累积）
                triggered_count = 0
                for i, sample in enumerate(abnormal_samples):
                    device_ip = sample.raw_data.get("device_ip") if sample.raw_data else None
                    abnormal_type = sample.abnormal_type

                    if not device_ip or not abnormal_type:
                        continue

                    # 检查是否应该触发研判（累积、去重、冷却）
                    should_trigger, reason = abnormal_tracker.should_trigger_diagnosis(
                        device_ip, abnormal_type, db_new, actual_site_id
                    )

                    if should_trigger:
                        logger.info(f"Triggering diagnosis for {device_ip} {abnormal_type}: {reason}")
                        try:
                            await automation_orchestrator.process_abnormal_sample(sample.id)
                            triggered_count += 1
                        except Exception as e:
                            logger.error(
                                f"Error processing abnormal sample {sample.id}: {e}",
                                exc_info=True
                            )
                    else:
                        logger.info(f"Skipping diagnosis for {device_ip} {abnormal_type}: {reason}")

                if triggered_count > 0:
                    logger.info(f"Triggered {triggered_count} diagnoses for {site.site_code}")
                    # 触发告警
                    from services.alert_service import alert_service
                    await alert_service.process_new_analysis_results(actual_site_id)
                else:
                    logger.info(f"No diagnoses triggered for {site.site_code} (all filtered by abnormal tracker)")

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
        3) 其余交给原有异常类型阈值匹配。
        """
        from services.abnormal_tracker import abnormal_tracker

        immediate_cfg = collection_policy.get("immediate_trigger", {})
        periodic_cfg = collection_policy.get("periodic_trigger", {})

        # 1) 严重事件实时触发
        immediate_checks = [
            ("critical_event_count", "CRITICAL_LOG_ALERT", "critical"),
            ("hardware_alarm_count", "HARDWARE_ISSUE", "critical"),
            ("auth_failure_count", "SECURITY_AUTH_FAILURE", "high"),
        ]
        for field, abnormal_type, risk_level in immediate_checks:
            val = int(stats.get(field, 0) or 0)
            threshold = int(immediate_cfg.get(field, 0) or 0)
            if threshold > 0 and val >= threshold:
                should, reason = abnormal_tracker.should_trigger_with_policy(
                    device_ip=device_ip,
                    abnormal_type=abnormal_type,
                    db=db,
                    site_id=site_id,
                    increment=val,
                    threshold=1,
                    window_minutes=60,
                    dedup_window_minutes=10,
                    cooldown_minutes=20
                )
                return {
                    "should_trigger": should,
                    "reason": f"[immediate] {reason}",
                    "trigger_mode": "immediate",
                    "matched_type_override": {
                        "type_code": abnormal_type,
                        "type_name": abnormal_type,
                        "risk_level": risk_level,
                        "enable_tracking": True,
                        "tracking_config": {}
                    } if should else None
                }

        # 2) 周期累计触发（例如接口up/down 30次/天）
        for field, cfg in periodic_cfg.items():
            val = int(stats.get(field, 0) or 0)
            if val <= 0:
                continue

            threshold = int(cfg.get("threshold", 0) or 0)
            window_minutes = int(cfg.get("window_minutes", 1440) or 1440)
            abnormal_type = cfg.get("abnormal_type", field.upper())
            if threshold <= 0:
                continue

            should, reason = abnormal_tracker.should_trigger_with_policy(
                device_ip=device_ip,
                abnormal_type=abnormal_type,
                db=db,
                site_id=site_id,
                increment=val,
                threshold=threshold,
                window_minutes=window_minutes,
                dedup_window_minutes=min(120, max(15, int(window_minutes / 12))),
                cooldown_minutes=min(240, max(30, int(window_minutes / 6)))
            )
            if should:
                return {
                    "should_trigger": True,
                    "reason": f"[periodic:{field}] {reason}",
                    "trigger_mode": "periodic",
                    "matched_type_override": {
                        "type_code": abnormal_type,
                        "type_name": abnormal_type,
                        "risk_level": cfg.get("risk_level", "medium"),
                        "enable_tracking": True,
                        "tracking_config": {}
                    }
                }

        # 3) 不拦截，让后续阈值匹配继续判断
        return {
            "should_trigger": True,
            "reason": "fallthrough_to_threshold_match",
            "trigger_mode": "fallback",
            "matched_type_override": None
        }
    
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

                    # 根据异常持续性调整风险等级
                    from services.abnormal_tracker import abnormal_tracker
                    base_severity = diagnosis_result.get("severity", "medium")
                    adjusted_severity = abnormal_tracker.calculate_severity_based_on_persistence(
                        device_ip=device_ip,
                        abnormal_type=diagnosis_result.get("diagnosis_type", "UNKNOWN"),
                        base_severity=base_severity,
                        site_id=site_id
                    )
                    diagnosis_result["severity"] = adjusted_severity
                    diagnosis_result["risk_level"] = adjusted_severity

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
                            "action": "query_devices",
                            "id": netbox_device_id
                        })
                        if result.success and result.data.get("count", 0) > 0:
                            devices = result.data.get("devices", [])
                            if devices:
                                device_info = devices[0]
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
