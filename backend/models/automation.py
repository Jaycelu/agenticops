"""
自动化中心数据库模型
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey,
    JSON, Index, Float, Numeric, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class AbnormalTypeStatus(str, enum.Enum):
    """异常类型状态枚举"""
    DRAFT = "DRAFT"           # 新建，未生效
    OBSERVED = "OBSERVED"     # 只统计，不触发研判
    ENABLED = "ENABLED"       # 正式进入自动化


class Site(Base):
    """基地信息表"""
    __tablename__ = "site"

    id = Column(Integer, primary_key=True, index=True)
    site_code = Column(String(50), unique=True, nullable=False, index=True)
    site_name = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    device_states = relationship("DeviceState", back_populates="site")
    log_samples = relationship("LogSample", back_populates="site")
    analysis_results = relationship("LogAnalysisResult", back_populates="site")
    automation_policies = relationship("AutomationPolicy", back_populates="site")
    automation_tasks = relationship("AutomationTask", back_populates="site")
    automation_switch = relationship("SiteAutomationSwitch", back_populates="site", uselist=False)


class SiteAutomationSwitch(Base):
    """基地自动化开关"""
    __tablename__ = "site_automation_switch"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    site = relationship("Site", back_populates="automation_switch")


class DeviceState(Base):
    """设备健康状态表"""
    __tablename__ = "device_state"

    id = Column(Integer, primary_key=True, index=True)
    netbox_device_id = Column(Integer, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    health_score = Column(Float, default=100.0)
    health_level = Column(String(20), default="normal")  # normal, warning, critical
    abnormal_flags = Column(JSON, default=list)  # 异常标志列表
    last_checked_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    site = relationship("Site", back_populates="device_states")

    # 索引
    __table_args__ = (
        Index('idx_device_state_site_netbox', 'site_id', 'netbox_device_id'),
    )


class AssetDevice(Base):
    """本地资产镜像（来自NetBox）"""
    __tablename__ = "asset_device"

    id = Column(Integer, primary_key=True, index=True)
    netbox_device_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(120), index=True)
    device_type = Column(String(120))
    site = Column(String(120), index=True)
    role = Column(String(120), index=True)
    vendor = Column(String(120), index=True)
    status = Column(String(50), index=True)
    serial = Column(String(120))
    primary_ip = Column(String(64), index=True)
    rack = Column(String(120))
    position = Column(String(32))
    face = Column(String(32))
    tags = Column(JSON, default=list)
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_asset_device_vendor_site", "vendor", "site"),
    )


class AlertEvent(Base):
    """统一告警事件表（供自动化中心消费）"""
    __tablename__ = "alert_event"

    id = Column(BigInteger, primary_key=True, index=True)
    source = Column(String(50), nullable=False, default="SPLUNK", index=True)
    external_event_id = Column(String(128), index=True)
    dedup_key = Column(String(64), nullable=False, unique=True, index=True)

    site_id = Column(Integer, ForeignKey("site.id"), nullable=True, index=True)
    netbox_device_id = Column(Integer, index=True)
    host = Column(String(255), index=True)
    name = Column(String(512), nullable=False)
    severity = Column(String(30), nullable=False, index=True)
    severity_level = Column(Integer, nullable=False, default=0, index=True)

    status = Column(String(30), nullable=False, default="open", index=True)  # open/acknowledged/resolved
    acknowledged = Column(Boolean, nullable=False, default=False, index=True)

    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True))
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    site = relationship("Site")

    __table_args__ = (
        Index("idx_alert_event_status_time", "status", "occurred_at"),
        Index("idx_alert_event_site_severity", "site_id", "severity_level"),
        Index("idx_alert_event_external_source", "source", "external_event_id"),
    )


class LocalTicket(Base):
    """本地工单表（用于系统内闭环与后续外部工单对接）"""
    __tablename__ = "local_ticket"

    id = Column(Integer, primary_key=True, index=True)
    ticket_code = Column(String(64), nullable=False, unique=True, index=True)
    provider = Column(String(32), nullable=False, default="local", index=True)
    event_id = Column(BigInteger, ForeignKey("alert_event.id"), nullable=True, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text)
    priority = Column(String(30), nullable=False, default="P3", index=True)
    requester = Column(String(120), nullable=False, default="netops-automation")
    status = Column(String(30), nullable=False, default="open", index=True)  # open, in_progress, resolved, closed
    ticket_metadata = Column("metadata", JSON, default=dict)
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    event = relationship("AlertEvent")

    __table_args__ = (
        Index("idx_local_ticket_status_time", "status", "created_at"),
        Index("idx_local_ticket_event_provider", "event_id", "provider"),
    )


class LogSample(Base):
    """日志采样表"""
    __tablename__ = "log_sample"

    id = Column(Integer, primary_key=True, index=True)
    netbox_device_id = Column(Integer, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)

    # 采样指标
    error_count = Column(Integer, default=0)
    crc_error_count = Column(Integer, default=0)
    flap_count = Column(Integer, default=0)
    neighbor_change_count = Column(Integer, default=0)

    # 采样时间窗口
    sampled_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    time_window_start = Column(DateTime(timezone=True))
    time_window_end = Column(DateTime(timezone=True))

    # 采样状态
    is_abnormal = Column(Boolean, default=False)
    abnormal_type = Column(String(50))  # LINK_QUALITY_DEGRADE, INTERFACE_FLAP, NEIGHBOR_CHANGE

    # 原始数据
    raw_data = Column(JSON)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    site = relationship("Site", back_populates="log_samples")
    analysis_results = relationship("LogAnalysisResult", back_populates="log_sample")

    # 索引
    __table_args__ = (
        Index('idx_log_sample_site_netbox_time', 'site_id', 'netbox_device_id', 'sampled_at'),
        Index('idx_log_sample_abnormal', 'site_id', 'is_abnormal', 'sampled_at'),
    )


class LogAnalysisResult(Base):
    """日志分析结果表"""
    __tablename__ = "log_analysis_result"

    id = Column(Integer, primary_key=True, index=True)
    netbox_device_id = Column(Integer, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    related_sample_id = Column(Integer, ForeignKey("log_sample.id"), index=True)

    # 分析类型与置信度
    analysis_type = Column(String(50))  # DIAGNOSIS, TREND_ANALYSIS
    confidence = Column(String(20))  # high, medium, low

    # 分析结果
    summary = Column(Text)
    severity = Column(String(20))  # info, warning, critical
    recommendation = Column(Text)

    # 证据数据
    evidence = Column(JSON)  # 日志证据、配置证据、对端证据

    # 状态
    status = Column(String(20), default="pending")  # pending, completed, failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    site = relationship("Site", back_populates="analysis_results")
    log_sample = relationship("LogSample", back_populates="analysis_results")

    # 索引
    __table_args__ = (
        Index('idx_analysis_site_device', 'site_id', 'netbox_device_id'),
        Index('idx_analysis_status', 'site_id', 'status', 'created_at'),
    )


class AutomationPolicy(Base):
    """自动化策略表"""
    __tablename__ = "automation_policy"

    id = Column(Integer, primary_key=True, index=True)
    policy_code = Column(String(100), unique=True, nullable=False, index=True)
    policy_name = Column(String(200))
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)

    # 策略类型与触发条件
    policy_type = Column(String(50))  # DIAGNOSIS, ALERT, EXECUTION
    trigger_type = Column(String(50))  # schedule, event, threshold
    trigger_condition = Column(JSON)  # 触发条件JSON

    # 策略动作
    action = Column(JSON)  # 动作定义JSON
    risk_level = Column(String(20), default="low")  # low, medium, high
    require_confirm = Column(Boolean, default=False)

    # 状态
    enabled = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    site = relationship("Site", back_populates="automation_policies")
    automation_tasks = relationship("AutomationTask", back_populates="policy")


class AutomationTask(Base):
    """自动化任务表"""
    __tablename__ = "automation_task"

    id = Column(Integer, primary_key=True, index=True)
    task_code = Column(String(100), unique=True, nullable=False, index=True)
    policy_id = Column(Integer, ForeignKey("automation_policy.id"), index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    netbox_device_id = Column(Integer, index=True)

    # 任务状态
    status = Column(String(30), default="pending")  # pending, running, waiting_confirm, success, failed, aborted

    # 触发原因
    triggered_by = Column(String(50))  # schedule, event, manual
    trigger_event = Column(JSON)

    # 决策与执行结果
    decision_result = Column(JSON)
    execution_result = Column(JSON)
    audit_trail = Column(JSON, default=list)
    need_human_confirm = Column(Boolean, default=False)

    # 时间记录
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    site = relationship("Site", back_populates="automation_tasks")
    policy = relationship("AutomationPolicy", back_populates="automation_tasks")
    action_logs = relationship("AutomationActionLog", back_populates="task")
    approvals = relationship("AutomationApproval", back_populates="task")
    feedbacks = relationship("AutomationTaskFeedback", back_populates="task")

    # 索引
    __table_args__ = (
        Index('idx_task_site_status', 'site_id', 'status', 'created_at'),
        Index('idx_task_policy', 'policy_id', 'created_at'),
    )


class AutomationActionLog(Base):
    """自动化执行日志表"""
    __tablename__ = "automation_action_log"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("automation_task.id"), nullable=False, index=True)

    # 执行信息
    action_type = Column(String(50))  # script, api, notification
    executor = Column(String(100))
    command = Column(Text)

    # 执行结果
    result = Column(JSON)
    success = Column(Boolean, default=False)
    error_message = Column(Text)

    # 时间
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    task = relationship("AutomationTask", back_populates="action_logs")


class AutomationApproval(Base):
    """自动化审批表（预留）"""
    __tablename__ = "automation_approval"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("automation_task.id"), nullable=False, index=True)

    # 审批信息
    approver = Column(String(100))
    decision = Column(String(20))  # approved, rejected
    comment = Column(Text)

    # 时间
    decided_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    task = relationship("AutomationTask", back_populates="approvals")


class AutomationTaskFeedback(Base):
    """自动化任务人工反馈表"""
    __tablename__ = "automation_task_feedback"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("automation_task.id"), nullable=False, index=True)

    # 反馈信息
    verdict = Column(String(30), nullable=False)  # correct, incorrect, partial
    comment = Column(Text)
    reviewer = Column(String(100), default="operator")
    tags = Column(JSON, default=list)

    # 时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    task = relationship("AutomationTask", back_populates="feedbacks")

    # 索引
    __table_args__ = (
        Index('idx_task_feedback_task_created', 'task_id', 'created_at'),
        Index('idx_task_feedback_verdict', 'verdict', 'created_at'),
    )


class AbnormalTrackerState(Base):
    """异常跟踪器持久化状态表"""
    __tablename__ = "abnormal_tracker_state"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=True, index=True)
    device_ip = Column(String(45), nullable=False, index=True)
    abnormal_type = Column(String(100), nullable=False, index=True)

    count = Column(Integer, default=0)
    first_abnormal_time = Column(DateTime(timezone=True))
    last_trigger_time = Column(DateTime(timezone=True))
    last_abnormal_time = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 索引
    __table_args__ = (
        Index(
            'uniq_abnormal_tracker_state',
            'site_id',
            'device_ip',
            'abnormal_type',
            unique=True
        ),
        Index('idx_abnormal_tracker_last_abnormal', 'last_abnormal_time'),
    )


class SSHCredential(Base):
    """SSH凭据表"""
    __tablename__ = "ssh_credential"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    username = Column(String(120), nullable=False)
    auth_type = Column(String(20), nullable=False, default="password")  # password / private_key
    encrypted_password = Column(Text)
    encrypted_private_key = Column(Text)
    encrypted_passphrase = Column(Text)
    port = Column(Integer, nullable=False, default=22)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    device_bindings = relationship("SSHCredentialDeviceBinding", back_populates="credential")


class SSHCredentialDeviceBinding(Base):
    """SSH凭据与设备关联表"""
    __tablename__ = "ssh_credential_device_binding"

    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(Integer, ForeignKey("ssh_credential.id"), nullable=False, index=True)
    netbox_device_id = Column(Integer, nullable=False, index=True)
    device_name = Column(String(120))
    site_name = Column(String(120))
    platform = Column(String(120))
    role = Column(String(120))
    tags = Column(JSON, default=list)
    last_connectivity_status = Column(String(30), default="unknown")  # unknown/success/failed/auth_failed
    last_connectivity_error = Column(Text)
    last_checked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    credential = relationship("SSHCredential", back_populates="device_bindings")

    __table_args__ = (
        Index("uniq_credential_device", "credential_id", "netbox_device_id", unique=True),
        Index("idx_binding_site_status", "site_name", "last_connectivity_status"),
    )


class CommandTemplate(Base):
    """厂商命令模板"""
    __tablename__ = "command_template"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    template_type = Column(String(80), nullable=False, default="diagnosis_default", index=True)
    vendor = Column(String(120), nullable=False, index=True)
    commands = Column(JSON, nullable=False, default=list)
    description = Column(Text)
    is_builtin = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_command_template_vendor_type", "vendor", "template_type"),
    )


class RawAnomaly(Base):
    """原始异常表 - 捕获行为偏离正常基线的异常"""
    __tablename__ = "raw_anomaly"

    id = Column(BigInteger, primary_key=True, index=True)
    
    # 基地和设备信息
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False, index=True)
    device_id = Column(BigInteger, index=True)
    device_ip = Column(String(45), nullable=False, index=True)
    
    # 时间窗口
    time_window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    time_window_end = Column(DateTime(timezone=True), nullable=False)
    
    # 日志模式指纹
    log_fingerprint = Column(String(64), nullable=False, index=True)
    
    # 原始日志样本（最多N条）
    log_samples = Column(JSON, nullable=False)
    
    # 当前窗口统计
    log_count = Column(Integer, nullable=False)
    
    # ===== Baseline 相关 =====
    baseline_avg_5m = Column(Numeric(10, 2))  # 历史平均（5分钟）
    baseline_p95_5m = Column(Numeric(10, 2))   # 历史 P95
    baseline_count_7d = Column(Integer)          # 7天出现次数
    deviation_ratio = Column(Numeric(6, 2))      # log_count / baseline_avg
    
    # ===== 分类与状态 =====
    pre_class = Column(String(64))  # Rule-based 预分类
    ai_class = Column(String(64))   # AI 分类
    severity = Column(String(16))   # low/medium/high
    confidence = Column(Numeric(4, 2))  # 0~1
    
    # 状态：NEW / CLASSIFIED / IGNORED / ESCALATED
    status = Column(String(32), nullable=False, default="NEW", index=True)
    
    # 时间记录
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 关系
    site = relationship("Site")
    
    # 索引
    __table_args__ = (
        Index('idx_raw_anomaly_site_time', 'site_id', 'time_window_start'),
        Index('idx_raw_anomaly_fingerprint', 'log_fingerprint'),
        Index('idx_raw_anomaly_status', 'site_id', 'status', 'first_seen_at'),
        Index('uniq_raw_anomaly_window', 'site_id', 'device_id', 'log_fingerprint', 'time_window_start', unique=True),
    )


class AbnormalType(Base):
    """异常类型管理表"""
    __tablename__ = "abnormal_type"

    id = Column(Integer, primary_key=True, index=True)
    type_code = Column(String(100), unique=True, nullable=False, index=True)  # 异常类型代码，如LINK_QUALITY_DEGRADE
    type_name = Column(String(200), nullable=False)  # 异常类型名称
    description = Column(Text)  # 异常类型描述
    
    # 状态：DRAFT / OBSERVED / ENABLED
    status = Column(String(20), nullable=False, default="DRAFT", index=True)
    
    # 异常特征
    fingerprint_pattern = Column(String(200))  # 日志指纹模式（用于UNKNOWN类型）
    keywords = Column(JSON)  # 关键词列表，如["CRC", "error"]
    
    # 阈值配置
    threshold_config = Column(JSON, nullable=False)  # 阈值配置，如{"count": 50, "time_window_minutes": 5}
    
    # 风险等级
    risk_level = Column(String(20), default="medium")  # low / medium / high
    
    # 是否启用异常跟踪
    enable_tracking = Column(Boolean, default=True)
    
    # 跟踪配置
    tracking_config = Column(JSON)  # 跟踪配置，如{"accumulation_threshold": 5, "dedup_window_minutes": 60, "cooldown_minutes": 60}
    
    # 统计信息
    occurrence_count = Column(Integer, default=0)  # 出现次数
    last_occurred_at = Column(DateTime(timezone=True))  # 最后出现时间
    
    # 创建和更新信息
    created_by = Column(String(100), default="system")
    updated_by = Column(String(100), default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_abnormal_type_status', 'status'),
        Index('idx_abnormal_type_risk', 'risk_level'),
    )
