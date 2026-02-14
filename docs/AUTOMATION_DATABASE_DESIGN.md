# NetOps 自动化中心数据库设计（PostgreSQL）

## 1. 目标

自动化中心采用独立数据库（推荐 `netops_automation`）存储高频日志采样、异常判定、研判任务、审计轨迹与反馈闭环数据，避免与业务资产查询数据混用。

- 引擎：PostgreSQL 14+
- ORM：SQLAlchemy
- 清理策略：应用内定时任务 + 可手动脚本

## 2. 逻辑分层

- `L0-配置与实体层`：站点、策略、异常类型、SSH 凭据
- `L1-观测层`：日志采样、原始异常
- `L2-研判层`：分析结果、决策上下文
- `L3-执行层`：自动化任务、动作日志、审批
- `L4-审计与学习层`：审计轨迹、人工反馈、统计学习

## 3. 核心表与字段

### 3.1 配置与实体层

1. `site`
- `id` PK
- `site_code` 唯一
- `site_name`
- `description`
- `created_at/updated_at`

2. `automation_policy`
- `id` PK
- `policy_code` 唯一
- `site_id` FK
- `policy_type`
- `trigger_type`
- `trigger_condition` JSON
- `action` JSON
- `risk_level`
- `require_confirm`
- `enabled`
- `created_at/updated_at`

3. `abnormal_type`
- `id` PK
- `type_code` 唯一
- `type_name`
- `description`
- `status` (`DRAFT/OBSERVED/ENABLED`)
- `keywords` JSON
- `threshold_config` JSON
- `risk_level`
- `enable_tracking`
- `tracking_config` JSON
- `occurrence_count`
- `last_occurred_at`

4. `ssh_credential`
- `id` PK
- `name` 唯一
- `username`
- `auth_type` (`password/private_key`)
- `encrypted_password`
- `encrypted_private_key`
- `encrypted_passphrase`
- `port`
- `enabled`
- `created_at/updated_at`

5. `ssh_credential_device_binding`
- `id` PK
- `credential_id` FK
- `netbox_device_id`
- `device_name/site_name/platform/role`
- `tags` JSON
- `last_connectivity_status`
- `last_connectivity_error`
- `last_checked_at`
- 唯一索引：`(credential_id, netbox_device_id)`

### 3.2 观测层

1. `log_sample`
- `id` PK
- `site_id` FK
- `netbox_device_id`
- `error_count/crc_error_count/flap_count/neighbor_change_count`
- `sampled_at`
- `time_window_start/time_window_end`
- `is_abnormal`
- `abnormal_type`
- `raw_data` JSON（含策略命中理由）

2. `raw_anomaly`
- `id` PK
- `site_id` FK
- `device_id/device_ip`
- `time_window_start/time_window_end`
- `log_fingerprint`
- `log_samples` JSON
- `log_count`
- `baseline_avg_5m/baseline_p95_5m/baseline_count_7d`
- `deviation_ratio`
- `pre_class/ai_class`
- `severity/confidence`
- `status`
- `first_seen_at/last_seen_at`

3. `abnormal_tracker_state`
- `id` PK
- `site_id`
- `device_ip`
- `abnormal_type`
- `count`
- `first_abnormal_time/last_trigger_time/last_abnormal_time`
- 唯一索引：`(site_id, device_ip, abnormal_type)`

### 3.3 研判与执行层

1. `log_analysis_result`
- `id` PK
- `site_id` FK
- `netbox_device_id`
- `related_sample_id`
- `analysis_type`
- `confidence`
- `summary`
- `severity`
- `recommendation`
- `evidence` JSON
- `status`

2. `automation_task`
- `id` PK
- `task_code` 唯一
- `policy_id` FK
- `site_id` FK
- `netbox_device_id`
- `status`
- `triggered_by`
- `trigger_event` JSON
- `decision_result` JSON
- `execution_result` JSON
- `audit_trail` JSON
- `need_human_confirm`
- `started_at/finished_at/created_at/updated_at`

3. `automation_action_log`
- `id` PK
- `task_id` FK
- `action_type/executor/command`
- `result` JSON
- `success`
- `error_message`
- `executed_at`

4. `automation_approval`
- `id` PK
- `task_id` FK
- `approver`
- `decision`
- `comment`
- `decided_at/created_at`

5. `automation_task_feedback`
- `id` PK
- `task_id` FK
- `verdict` (`correct/incorrect/partial`)
- `comment`
- `reviewer`
- `tags` JSON
- `created_at/updated_at`

## 4. 保留策略（默认）

- `raw_anomaly`: 30天
- `log_sample`: 30天
- `log_analysis_result`: 60天
- `automation_task`: 90天
- `automation_action_log`: 90天
- `automation_approval`: 180天
- `automation_task_feedback`: 180天
- `abnormal_tracker_state`: 7天

由 `backend/services/data_retention_service.py` 执行，后端每12小时自动清理一次。

## 5. 初始化与运维

### 初始化

```bash
cd backend
source venv/bin/activate
python3 scripts/init_automation_db.py
```

### 手动清理

```bash
cd backend
source venv/bin/activate
python3 scripts/cleanup_automation_data.py
```

## 6. 推荐索引与扩展

- 高基数时间字段：`sampled_at`, `created_at`, `executed_at` 建议加 BTREE 索引
- 高频 JSON 检索字段（如 `decision_result->context->device_ip`）建议拆列冗余
- 日志量持续增长时建议按月分区：`log_sample`, `raw_anomaly`, `automation_action_log`
- 大文本证据建议冷热分层：7天热数据在主库，历史归档到对象存储
