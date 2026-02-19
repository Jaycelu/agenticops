# Runbook

## 1. 适用范围

本手册用于 NetOps 事件中心迁移后的日常运行、验证、排障与发布，覆盖后端 FastAPI、前端 Vue、事件链路与自动化中心联动。

## 2. 运行前检查

1. Python 3.11+ 可用（建议 `python3`）。
2. Node.js 与 npm 可用。
3. 后端依赖已安装：
- `cd backend && pip3 install -r requirements.txt`
4. 前端依赖已安装：
- `cd frontend && npm install`

## 3. 关键配置

配置文件：`backend/.env`（可由 `deploy/env.example` 复制）。

关键项：
1. 数据库：`DATABASE_URL` / `AUTOMATION_DATABASE_URL`
2. 安全开关：`automation_observe_only=true`
3. 外部系统：`NETBOX_*`, `ZABBIX_*`, `ELK_*`
4. 工单预留：`ticket_system_*`（当前可留空，使用 mock）

## 4. 启动流程

### 4.1 后端

```bash
cd backend
python3 main.py
```

健康检查：
- `GET http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

### 4.2 前端

```bash
cd frontend
npm run dev
```

默认访问：`http://localhost:5173`

## 5. 发布前强制验证

### 5.1 后端契约测试

```bash
cd backend
python3 -m unittest tests/test_core_api_contracts.py
```

期望：`Ran 6 tests ... OK`

### 5.2 前端构建

```bash
cd frontend
npm run build
```

期望：`vite build` 成功且无 TS 错误。

## 6. 事件中心联调步骤

1. 查询模式：
- `GET /api/events/mode`
- 确认返回 `observe_only`。

2. 注入测试事件：
- `POST /api/events/ingest`
- 最小体：`source`, `event_type`, `name`。

3. 查询事件：
- `GET /api/events?limit=20`
- 确认事件入库。

4. 触发只读研判：
- `POST /api/events/{id}/dispatch-readonly`
- 期望返回 `task_id`。

5. 查看关联：
- `GET /api/events/{id}/relations`
- 期望 `linked_tasks` 包含对应任务，状态进入 `waiting_confirm` 或后续状态。

6. 创建工单（预留）：
- `POST /api/events/{id}/ticket`
- 当前 mock 模式下期望 `ticket_id` 形如 `LOCAL-*`。

7. 前端联动核对：
- 事件详情显示 `recommended_skill_code`
- 任务状态徽标可见
- 点击“查看任务详情”可跳转 `/automation/tasks/:id`

## 7. 故障排查

### 7.1 后端测试失败：`No module named sqlalchemy`

原因：依赖未安装。
处理：
```bash
cd backend
pip3 install -r requirements.txt
```

### 7.2 只读派发失败：`Event missing site_id`

原因：事件没有 `site_id`，无法创建自动化任务。
处理：
1. 事件接入时补齐 `site_id`
2. 或先建立事件到站点映射规则后再派发

### 7.3 dispatch 成功但 relations 无任务

排查：
1. 检查 `automation_task` 是否创建成功
2. 确认 `trigger_event.source_type == AlertEvent`
3. 确认 `trigger_event.source_id == event_id`

### 7.4 动作被 observe-only 阻断

现象：执行结果 `ABORTED` 且提示非只读动作被拦截。
处理：
1. 保持 `observe_only` 不变（生产建议）
2. 将 action 配置标记为 `read_only=true`

## 8. 变更策略（持续执行）

1. 一次只处理一类问题（类型修复/契约修复/文档修复）。
2. 保持 `observe_only=true`，禁止下发路径回归。
3. 每批结束输出状态快照：
- 完成项
- 未完成项
- 阻塞项
- 下一条命令

## 9. 回滚策略

1. 前端异常：回退对应页面/API 提交；确保 `npm run build` 恢复。
2. 后端异常：优先回退 API 行为变更；保证 `test_core_api_contracts.py` 通过。
3. 数据层：本阶段未引入破坏性迁移，按服务回滚即可。

## 10. 交接清单

交接前确认：
1. `backend/tests/test_core_api_contracts.py` 最新且通过。
2. `frontend` 构建成功。
3. 事件中心关键页面可用：列表、详情、只读派发、关联跳转。
4. 本文档与 `docs/EVENTS_MIGRATION_PLAN.md` 已更新。

