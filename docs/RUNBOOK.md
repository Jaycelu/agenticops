# Runbook

## 首个管理员初始化

数据库迁移完成后，只允许在空用户库中执行一次初始化。密码只能通过进程环境传入，命令不会接受明文密码参数：

```bash
cd backend
BOOTSTRAP_ADMIN_PASSWORD='使用密码管理器生成的长随机密码' \
  python -m scripts.bootstrap_admin \
  --username admin \
  --display-name Administrator \
  --confirm-create-first-admin
unset BOOTSTRAP_ADMIN_PASSWORD
```

命令会创建并启用 `local` 紧急身份源、首个管理员及审计事件。发现任何已有用户时会拒绝执行。日常访问应配置 OIDC、LDAP/AD 或 SAML；本地紧急管理员只用于身份源故障恢复。

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
1. 数据库：`DATABASE_URL`（必须为 `postgresql://`，所有业务域共用一个逻辑数据库）
2. 安全开关：`automation_observe_only=true`
3. SSO 回调：`AUTH_PUBLIC_BASE_URL`（必须为对外可访问的 HTTPS 根地址）
4. 外部系统：`NETBOX_*`, `ELK_*`
5. 工单配置：`TICKET_MODE=local`（当前固定本地工单闭环）；`ticket_system_*` 仅做后续外部对接预留

CI 使用独立的 `netops_agenticops_test` 测试库并会清理其中数据；它不是生产部署的第二个数据库，也绝不能指向生产库。

浏览器状态变更请求必须同时携带 Session Cookie、CSRF Cookie 及同值的 `X-CSRF-Token` 请求头。ELK/Zabbix 等机器事件接入不使用浏览器 Session，只接受具有 `events.ingest` 权限的 Bearer API Token；机器 Token 不能获得审批或执行权限。

## 4. 启动流程

### 4.1 数据库迁移、API 与 Worker

```bash
export APP_SECRET_KEY='至少 32 字节的随机值'
export POSTGRES_PASSWORD='数据库随机密码'
docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d backend worker frontend
```

健康检查：
- API 存活：`GET http://localhost:8000/health/live`
- API 就绪（数据库与迁移版本）：`GET http://localhost:8000/health/ready`
- 依赖状态（含 Worker、SSO、ELK checkpoint）：`GET http://localhost:8000/health/dependencies`
- Prometheus 指标：`GET http://localhost:8000/metrics`
- Worker：`docker compose exec worker python -m scripts.check_worker_health`
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

### 5.3 完整发布门禁

生产 Release 不能只做语法和前端构建。还必须执行 PostgreSQL 测试、Alembic 校验、迁移往返、Ruff、Bandit、pip-audit、Compose 构建与全栈健康检查，具体命令和责任边界见 [RELEASE_PRECHECK.md](./RELEASE_PRECHECK.md)。

## 6. 事件中心联调步骤

1. 查询模式：
- `GET /api/events/mode`
- 确认返回 `observe_only`。

2. 注入测试事件：
- `POST /api/events/ingest`
- 最小体：`source`, `event_type`, `name`。
- 仅接受：`source=ELK,event_type=log_signal` 或 `source=ZABBIX,event_type=zabbix_alert`。
- 请求头：`Authorization: Bearer <events.ingest API Token>`。

3. 查询事件：
- `GET /api/events?limit=20`
- 确认事件入库。

4. 触发只读研判：
- `POST /api/events/{id}/dispatch-readonly`
- 期望返回 `case_id/case_code` 并创建 Case。后续 Agent Graph 由 Worker 异步推进，不能把 HTTP 返回当作诊断完成。

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

## 7. Agent Graph 日常操作

### 7.1 创建或复用运行

在 Case 详情页点击“运行智能体”，或调用：

```text
POST /api/cases/{case_id}/run-agents
```

正常响应为 `202 Accepted`，含 `graph_run_id`、`current_state`、`current_node`、`queued` 和 `already_running`。同一 Case 已有活动运行时会幂等复用，不应手工重复创建任务。

轮询与审计使用：

```text
GET /api/cases/{case_id}/graph-runs
GET /api/cases/{case_id}/graph-runs/{graph_run_id}
GET /api/cases/{case_id}/timeline
GET /api/cases/{case_id}/hypotheses
GET /api/cases/{case_id}/agent-budget
```

Graph Run 状态包括 `queued`、`running`、`waiting_evidence`、`waiting_human`、`paused`、`completed`、`failed`、`cancelled`、`timed_out` 和 `budget_exhausted`。

### 7.2 Worker 重启与恢复

Worker 被中断时不要删除任务或直接修改 Case 状态。先恢复数据库连接并启动 Worker：

```bash
docker compose up -d worker
docker compose exec worker python -m scripts.check_worker_health
docker compose logs --tail=200 worker
```

健康 Worker 会接管过期 Graph 租约并从 Checkpoint/持久化任务继续。核对 `case_graph_resume_total`、Graph Run 的当前节点和 Timeline；若租约未过期，应等待 `AGENT_GRAPH_LEASE_SECONDS`，不要并发启动绕过租约的脚本。

### 7.3 Evidence、凭据与人工等待

- `waiting_evidence`：检查 Timeline 中 Evidence Request、Probe ID、目标范围、Policy 决策和 Tool Call 错误；Agent 不允许提交原始 Shell。
- `waiting_human`：通常表示凭据缺失、目标不存在或根因无法确认。补齐真实前置条件并保留原审计记录，不要直接改数据库状态。
- `budget_exhausted`：检查耗尽资源和重复任务，修复无法收敛的原因后再受控重跑；不要默认提高全局预算。
- 多来源证据冲突：查看 Hypothesis Board 的支持证据、反证、时效和 Critic 结论，未满足确认阈值时应升级人工。

### 7.4 强制重跑

只有具备 `agent_graphs.restart` 权限的人员可以调用：

```text
POST /api/cases/{case_id}/run-agents?force_restart=true
```

操作会取消旧 Graph Run、保留旧 Checkpoint、Evidence、Claim、Hypothesis 和 Timeline，创建新 `graph_run_id` 并写审计。强制重跑不能绕过 PolicyGuard、审批或 Observe-only。

兼容旧客户端时可以使用 `wait=true&timeout_seconds=30`。等待有上限，超时后 Graph Job 继续运行；前端和自动化系统仍应保存 `graph_run_id` 并轮询。

## 8. 故障排查

### 8.1 后端测试失败：`No module named sqlalchemy`

原因：依赖未安装。
处理：
```bash
cd backend
pip3 install -r requirements.txt
```

### 8.2 只读派发失败：`Event missing site_id`

原因：事件没有 `site_id`，无法补齐完整 Case/Fabric 上下文。
处理：
1. 事件接入时补齐 `site_id`
2. 或先建立事件到站点映射规则后再派发

### 8.3 dispatch 成功但 relations 无结果

排查：
1. 检查 `source_event` 详情是否已写入 `case / dispatch / ticket` 摘要
2. 确认 `source_event.normalized_payload.case.case_id` 已写入
3. 确认 `fabric` 侧 `remediation_plan / execution_run` 已生成

### 8.4 动作被 observe-only 阻断

现象：执行结果 `ABORTED` 且提示非只读动作被拦截。
处理：
1. 保持 `observe_only` 不变（生产建议）
2. 将 action 配置标记为 `read_only=true`

### 8.5 Graph 长时间停在 queued

排查：

1. `docker compose exec worker python -m scripts.check_worker_health`
2. 检查 Worker 和数据库日志，确认迁移 head 一致。
3. 检查是否存在未过期租约；不要直接删除租约或任务。
4. 查看 Budget 是否已耗尽，以及 Case 是否正在 `waiting_human`。

### 8.6 Probe 被 PolicyGuard 拒绝

这是安全失败，不应绕过。确认目录项同时为 `agent_selectable=true`、`read_only=true`，目标在允许范围，厂商受支持，参数符合白名单 Schema，并且凭据只拥有 `probe.read`。`api.request`、`script.run`、`ssh.config_change` 不能作为 Agent 自主选择工具。

## 9. 变更策略（持续执行）

1. 一次只处理一类问题（类型修复/契约修复/文档修复）。
2. 保持 `observe_only=true`，禁止下发路径回归。
3. 每批结束输出状态快照：
- 完成项
- 未完成项
- 阻塞项
- 下一条命令

## 10. 回滚策略

1. 变更前执行 `pg_dump -Fc`，记录应用提交 SHA 和 Alembic revision。
2. 应用异常但 schema 兼容：回退镜像/提交，保持 `AUTOMATION_OBSERVE_ONLY=true`，重启 API 与 Worker。
3. schema 不兼容：停止 API/Worker，将备份恢复到新建的空数据库，切换 `DATABASE_URL`；不要在原生产库上反复 downgrade/upgrade。
4. Webhook 或设备动作异常：先停 Worker，再禁用 Endpoint/变更策略；API 可继续提供只读查询。
5. 恢复后验证 `/health/ready`、Worker heartbeat、审计链、待投递队列与 checkpoint，再恢复流量。

详细命令和放量门禁见 `docs/PRODUCTION_DEPLOYMENT.md`。

## 11. 交接清单

交接前确认：
1. 后端 `python3 -m compileall .` 通过。
2. `frontend` 构建成功。
3. 事件中心关键页面可用：列表、详情、只读派发、关联跳转。
4. 工单页面可用：`/tickets`（列表与状态更新）。
5. 本文档与 `docs/EVENTS_MIGRATION_PLAN.md` 已更新。
6. Agent Graph 可异步受理、轮询、写 Timeline，并在 Worker 重启后恢复。
7. Budget、Hypothesis、Critic 和 Tool Call 审计数据可从 Case 页面及 API 查询。
8. `AUTOMATION_OBSERVE_ONLY=True`，未执行任何真实设备变更。
