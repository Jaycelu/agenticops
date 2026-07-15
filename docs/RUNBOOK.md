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

1. 变更前执行 `pg_dump -Fc`，记录应用提交 SHA 和 Alembic revision。
2. 应用异常但 schema 兼容：回退镜像/提交，保持 `AUTOMATION_OBSERVE_ONLY=true`，重启 API 与 Worker。
3. schema 不兼容：停止 API/Worker，将备份恢复到新建的空数据库，切换 `DATABASE_URL`；不要在原生产库上反复 downgrade/upgrade。
4. Webhook 或设备动作异常：先停 Worker，再禁用 Endpoint/变更策略；API 可继续提供只读查询。
5. 恢复后验证 `/health/ready`、Worker heartbeat、审计链、待投递队列与 checkpoint，再恢复流量。

详细命令和放量门禁见 `docs/PRODUCTION_DEPLOYMENT.md`。

## 10. 交接清单

交接前确认：
1. 后端 `python3 -m compileall .` 通过。
2. `frontend` 构建成功。
3. 事件中心关键页面可用：列表、详情、只读派发、关联跳转。
4. 工单页面可用：`/tickets`（列表与状态更新）。
5. 本文档与 `docs/EVENTS_MIGRATION_PLAN.md` 已更新。
