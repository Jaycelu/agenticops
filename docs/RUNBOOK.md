# Runbook

## 1. 适用范围

本手册用于 NetOps 事件中心迁移后的日常运行、验证、排障与发布，覆盖后端 FastAPI、前端 Vue、事件链路与 Case/Fabric 联动。

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
1. 数据库：`DATABASE_URL` / `AUTOMATION_DATABASE_URL`（必须为 `postgresql://`）
2. 安全开关：`automation_observe_only=true`
3. 外部系统：`NETBOX_*`, `ELK_*`
4. 工单配置：`TICKET_MODE=local`（当前固定本地工单闭环）；`ticket_system_*` 仅做后续外部对接预留

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

### 5.1 后端语法检查

```bash
cd backend
python3 -m compileall .
```

期望：无语法错误。

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
- 仅接受：`source=ELK,event_type=log_signal` 或 `source=ZABBIX,event_type=zabbix_alert`。

3. 查询事件：
- `GET /api/events?limit=20`
- 确认事件入库。

4. 触发只读研判：
- `POST /api/events/{id}/dispatch-readonly`
- 期望返回 `case_id/case_code`，并进入 Case pipeline。

5. 查看关联：
- `GET /api/events/{id}/relations`
- 期望 `linked_case` 与 `linked_tasks` 返回 Case/Fabric 关联结果。

6. 创建工单：
- `POST /api/events/{id}/ticket`
- 默认本地工单模式下期望 `ticket_id` 形如 `LOCAL-*`。

7. 查询本地工单：
- `GET /api/tickets`
- `PATCH /api/tickets/{ticket_code}` 更新状态。

7. 前端联动核对：
- 事件详情显示 `recommended_skill_code`
- 任务状态徽标可见
- 点击“查看执行建议”进入 `/fabric`

## 7. 故障排查

### 7.1 后端测试失败：`No module named sqlalchemy`

原因：依赖未安装。
处理：
```bash
cd backend
pip3 install -r requirements.txt
```

### 7.2 只读派发失败：`Event missing site_id`

原因：事件没有 `site_id`，无法补齐完整 Case/Fabric 上下文。
处理：
1. 事件接入时补齐 `site_id`
2. 或先建立事件到站点映射规则后再派发

### 7.3 dispatch 成功但 relations 无结果

排查：
1. 检查 `source_event` 详情是否已写入 `case / dispatch / ticket` 摘要
2. 确认 `source_event.normalized_payload.case.case_id` 已写入
3. 确认 `fabric` 侧 `remediation_plan / execution_run` 已生成

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
2. 后端异常：优先回退 API 行为变更；保证 `python3 -m compileall .` 通过。
3. 数据层：本阶段未引入破坏性迁移，按服务回滚即可。

## 10. 交接清单

交接前确认：
1. 后端 `python3 -m compileall .` 通过。
2. `frontend` 构建成功。
3. 事件中心关键页面可用：列表、详情、只读派发、关联跳转。
4. 工单页面可用：`/tickets`（列表与状态更新）。
5. 本文档与 `docs/EVENTS_MIGRATION_PLAN.md` 已更新。
