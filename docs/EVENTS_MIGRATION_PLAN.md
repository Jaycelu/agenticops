# Events Migration Plan

## 1. 背景与目标

当前已完成事件主链路向 Source-Centric 模型迁移，核心目标是将处理路径统一为“事件驱动 + Case pipeline + Fabric 执行建议 + 本地工单闭环”的稳态架构，并保持 `observe_only=true` 安全约束。

本阶段文档用于固化：
1. 架构与边界
2. 接口契约
3. 运行与验证步骤
4. 已知限制
5. 下一阶段计划

## 2. 当前基线（截至本次交付）

1. 事件中心主链路已上线：接入、只读派发、工单创建、关联查询。
2. 旧告警主链路已移除：
- `backend/api/alerts.py`
- `frontend/src/pages/Alerts.vue`
3. 前端 TS 类型债务首批已清理，构建恢复：`npm run build` 通过。
4. 事件中心前端能力已补齐：
- 事件详情展示 `recommended_skill_code`
- 关联任务状态徽标
- 事件详情可跳转到 `Case / Fabric`
5. 后端契约测试已增强并通过：
- 事件 ingest/list
- 本地工单模式
- relations 状态流转
- observe-only 执行保护

## 3. 目标架构

### 3.1 架构总览

- 入口：`POST /api/events/ingest`
- 事件存储：`source_event`
- 只读派发：`POST /api/events/{event_id}/dispatch-readonly`
- Case 链路：`case_record -> remediation_plan -> execution_run`
- 工单：`POST /api/events/{event_id}/ticket`（默认落本地工单表）
- 关系聚合：`GET /api/events/{event_id}/relations`

### 3.2 安全边界

1. 全局保持 `automation_observe_only=true`（`backend/config/settings.py`）。
2. 执行引擎保护：`services/execution_engine.py` 在 observe-only 下阻断非 `read_only` 动作。
3. 事件派发固定为“只读研判 + 人工确认前置”。

## 4. 数据模型与字段约定

### 4.1 事件（SourceEvent）

核心字段：
- 标识：`id`, `source`, `external_event_id`, `dedup_key`
- 关联：`site_id`, `netbox_device_id`, `host`
- 状态：`status` (`open|acknowledged|resolved`), `acknowledged`
- 内容：`name`, `severity`, `severity_level`, `payload`
- 时间：`occurred_at`, `last_seen_at`, `resolved_at`

### 4.2 payload 约定

在 `payload` 中预留并维护：
- `case`：最近一次 Case 摘要（`case_id`, `case_code`, `created_at`）
- `dispatch`：最近一次只读派发摘要（`mode`, `case_id`, `case_code`, `dispatched_at`）
- `ticket`：工单摘要（`ticket_id`, `provider`, `status`, `created_at`）
- `recommended_skill_code`：推荐 skill 编码（可选）

## 5. API 契约（现行）

### 5.1 模式
- `GET /api/events/mode`
- 返回：`observe_only | normal`

### 5.2 接入
- `POST /api/events/ingest`
- 行为：幂等去重（`external_event_id/fingerprint/时间桶`）并 upsert。
- 限定：仅接受 `ELK/log_signal` 与 `ZABBIX/zabbix_alert` 两类规范化输入。

### 5.3 查询
- `GET /api/events`
- 支持：`status`, `severity`, `source`, `site_id`, `netbox_device_id`, `skip`, `limit`

### 5.4 只读派发
- `POST /api/events/{event_id}/dispatch-readonly`
- 结果：创建或绑定 Case，自动生成 Playbook 草稿与 check 结果，并转入 Case pipeline。

### 5.4.1 Playbook 草稿校验
- `POST /api/events/{event_id}/playbook-draft-check`
- 行为：按事件上下文生成 Ansible Playbook 草稿（只读诊断命令），执行 YAML/结构校验并返回 check 结果（不执行配置变更）。

### 5.5 工单
- `POST /api/events/{event_id}/ticket`
- 当前：默认创建本地工单记录并返回 `LOCAL-*` 工单号。
- `GET /api/tickets`：查询本地工单列表。
- `PATCH /api/tickets/{ticket_code}`：更新本地工单状态。

### 5.6 关联查询
- `GET /api/events/{event_id}/relations`
- 返回：`ticket` + `linked_case` + `linked_tasks[]`（按 Fabric 执行建议时间倒序聚合）

## 6. 前端实现对齐

相关文件：
- `frontend/src/pages/Events.vue`
- `frontend/src/api/events.ts`

已实现：
1. 事件详情显示推荐 skill。
2. 关联任务展示状态徽标。
3. 一键跳转到 Case/Fabric 工作台。

## 7. 测试与发布基线

每次提交必须满足：
1. 后端：`python3 -m compileall .`
2. 前端：`npm run build`

本次结果：
1. 后端：`python3 -m compileall .` 通过
2. 前端：`vite build ... ✓ built`

## 8. 已知限制

1. 外部工单系统尚未接入，当前以本地工单模块为默认闭环。
2. `relations` 当前仍有部分基于 payload 的兼容读取，后续可继续收敛为更强约束的规范字段。
3. `recommended_skill_code` 目前以上下文字段/`payload` 为主，后续建议统一持久化到规范字段。

## 9. 下一阶段计划

### P3.1 稳态增强
1. 为事件 -> 任务 -> 执行审计补充端到端追踪标识（trace_id/span_id）。
2. 增加 `relations` 分页与状态过滤。

### P3.2 工单系统接入（保持开关可控）
1. 维持“默认 local，按环境启用 external provider”。
2. 外部对接契约见 `docs/TICKET_INTEGRATION_GUIDE.md`。

### P3.3 可观测性
1. 增加事件派发成功率、任务等待确认时长、工单创建成功率指标。
2. 将关键异常写入统一审计日志。
