# Events Migration Plan

## 1. 背景与目标

当前已完成告警主链路向事件中心迁移，核心目标是将“告警处理”统一为“事件驱动 + 只读研判 + 任务联动 + 工单预留”的稳态架构，并保持 `observe_only=true` 安全约束。

本阶段文档用于固化：
1. 架构与边界
2. 接口契约
3. 运行与验证步骤
4. 已知限制
5. 下一阶段计划

## 2. 当前基线（截至本次交付）

1. 事件中心主链路已上线：接入、只读派发、工单预留、关联查询。
2. 旧告警主链路已移除：
- `backend/api/alerts.py`
- `frontend/src/pages/Alerts.vue`
3. 前端 TS 类型债务首批已清理，构建恢复：`npm run build` 通过。
4. 事件中心前端能力已补齐：
- 事件详情展示 `recommended_skill_code`
- 关联任务状态徽标
- 事件详情跳转任务详情 `/automation/tasks/:id`
5. 后端契约测试已增强并通过：
- 事件 ingest/list
- 工单 mock 模式
- relations 状态流转
- observe-only 执行保护

## 3. 目标架构

### 3.1 架构总览

- 入口：`POST /api/events/ingest`
- 事件存储：`alert_event`
- 只读派发：`POST /api/events/{event_id}/dispatch-readonly`
- 任务链路：`automation_task`（`trigger_event.source_type=AlertEvent`）
- 工单预留：`POST /api/events/{event_id}/ticket`（当前本地 mock）
- 关系聚合：`GET /api/events/{event_id}/relations`

### 3.2 安全边界

1. 全局保持 `automation_observe_only=true`（`backend/config/settings.py`）。
2. 执行引擎保护：`services/execution_engine.py` 在 observe-only 下阻断非 `read_only` 动作。
3. 事件派发固定为“只读研判 + 人工确认前置”。

## 4. 数据模型与字段约定

### 4.1 事件（AlertEvent）

核心字段：
- 标识：`id`, `source`, `external_event_id`, `dedup_key`
- 关联：`site_id`, `netbox_device_id`, `host`
- 状态：`status` (`open|acknowledged|resolved`), `acknowledged`
- 内容：`name`, `severity`, `severity_level`, `payload`
- 时间：`occurred_at`, `last_seen_at`, `resolved_at`

### 4.2 payload 约定

在 `payload` 中预留并维护：
- `task`：最近一次派发任务摘要（`task_id`, `task_code`, `status`, `created_at`）
- `ticket`：工单摘要（`ticket_id`, `provider`, `status`, `created_at`）
- `recommended_skill_code`：推荐 skill 编码（可选）

## 5. API 契约（现行）

### 5.1 模式
- `GET /api/events/mode`
- 返回：`observe_only | normal`

### 5.2 接入
- `POST /api/events/ingest`
- 行为：幂等去重（`external_event_id/fingerprint/时间桶`）并 upsert。

### 5.3 查询
- `GET /api/events`
- 支持：`status`, `severity`, `source`, `site_id`, `netbox_device_id`, `skip`, `limit`

### 5.4 只读派发
- `POST /api/events/{event_id}/dispatch-readonly`
- 结果：创建自动化任务，状态推进至 `waiting_confirm`。

### 5.5 工单预留
- `POST /api/events/{event_id}/ticket`
- 当前：本地 mock 适配器返回 `LOCAL-*` 工单号。

### 5.6 关联查询
- `GET /api/events/{event_id}/relations`
- 返回：`ticket` + `linked_tasks[]`（按任务创建时间倒序聚合）

## 6. 前端实现对齐

相关文件：
- `frontend/src/pages/Events.vue`
- `frontend/src/api/events.ts`

已实现：
1. 事件详情显示推荐 skill。
2. 关联任务展示状态徽标。
3. 一键跳转任务详情 `/automation/tasks/:id`。

## 7. 测试与发布基线

每次提交必须满足：
1. 后端：`python3 -m unittest tests/test_core_api_contracts.py`
2. 前端：`npm run build`

本次结果：
1. 后端：`Ran 6 tests ... OK`
2. 前端：`vite build ... ✓ built`

## 8. 已知限制

1. 工单系统仍为 mock 预留，尚未对接真实工单平台。
2. `relations` 当前采用 Python 侧筛选 JSON `trigger_event`（DB-agnostic），后续可优化为数据库原生 JSON 查询。
3. `recommended_skill_code` 目前以上下文字段/`payload` 为主，后续建议统一持久化到规范字段。

## 9. 下一阶段计划

### P3.1 稳态增强
1. 为事件 -> 任务 -> 执行审计补充端到端追踪标识（trace_id/span_id）。
2. 增加 `relations` 分页与状态过滤。

### P3.2 工单系统接入（保持开关可控）
1. 在 `ticket_adapter` 增加 provider 配置层。
2. 保持“默认 mock，按环境启用真实 provider”。

### P3.3 可观测性
1. 增加事件派发成功率、任务等待确认时长、工单创建成功率指标。
2. 将关键异常写入统一审计日志。

