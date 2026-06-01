"""
事件路由与端到端链路共用阈值（与 site_config.DEFAULT_SAMPLING_CONFIG 配合运维）。

- 采样侧：见 DEFAULT_SAMPLING_CONFIG['abnormal_tracker']、thresholds、log_collection_policy
- 事件中心 enrich：见下方常量（与 EventDecisionService.enrich_decision_for_context 一致）
"""

# 24h 窗口内同锚点事件计数：noise -> ticket_only
CLUSTER_COUNT_NOISE_TO_TICKET = 10

# 24h 窗口内同锚点事件计数：noise/ticket_only -> case_required
CLUSTER_COUNT_TO_CASE = 25

# 跨源关联：与当前事件相反来源（日志<->告警）在同一设备/主机上的时间窗（分钟）
CROSS_SOURCE_WINDOW_MINUTES = 30

# 时间窗内存在至少多少个「对端源」事件时，可对 ticket_only 升格（与日志+监控交叉确认设计一致）
CROSS_SOURCE_PEER_BOOST_MIN = 1

# Phase 1 execution safety: block repeated automated actions on the same target.
EXECUTION_CIRCUIT_BREAKER_WINDOW_MINUTES = 30
EXECUTION_CIRCUIT_BREAKER_MAX_RUNS = 3

# Phase 4.B topology correlation (derivative-alarm suppression):
# only correlate a new device's signal to an open upstream case opened within this window.
TOPOLOGY_CORRELATION_WINDOW_MINUTES = 30
# max hops to walk upward (toward core) when searching for an upstream open case.
TOPOLOGY_CORRELATION_MAX_HOPS = 2
