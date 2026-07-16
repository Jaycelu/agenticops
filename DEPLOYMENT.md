# AgenticOps 部署手册

本文是安装、初始化和升级的唯一完整入口。生产运行、备份恢复与放量策略见 [docs/PRODUCTION_DEPLOYMENT.md](./docs/PRODUCTION_DEPLOYMENT.md)，接口联调与日常排障见 [docs/RUNBOOK.md](./docs/RUNBOOK.md)。

## 1. 部署拓扑与前置条件

标准 Compose 拓扑包含：

- 一个 PostgreSQL 16 逻辑数据库 `netops_agenticops`；所有业务域共用该库。
- 一次性 `migrate` 迁移任务。
- `backend` API 和独立 `worker`。
- `frontend` Nginx 静态站点及 `/api` 反向代理。

主机至少需要 Git、Docker Engine 24+、Docker Compose v2、`curl` 和 `openssl`。生产环境还需要：

- 一个解析到 HTTPS 入口的域名。
- 由反向代理或负载均衡提供的有效 TLS 证书；本仓库不包含证书签发。
- 能访问 NetBox、ELK、Zabbix、LLM、设备管理网和 Webhook 接收端的网络路径。
- 数据库备份目录和外部监控系统。

建议先从单节点部署开始。3000 台以内设备、每日约 10 万条日志不需要拆分第二个数据库；容量瓶颈应先通过 Worker 指标和 checkpoint lag 验证。

## 2. 获取代码

```bash
git clone https://github.com/Jaycelu/agenticops.git
cd agenticops
git fetch --tags --prune
git checkout v0.2.0
```

生产环境应部署已验证的 Release tag，不要直接跟随开发分支。确认标签与提交并记录到变更单：

```bash
git describe --tags --exact-match
git rev-parse HEAD
```

Compose 项目名已在 `docker-compose.yml` 中固定为 `agenticops`，不会再随部署目录名变化。由旧版 `netops_bs` Compose 项目升级时，先按生产运行手册备份数据库；不要直接执行 `docker compose down -v`，旧命名卷需要单独迁移或显式挂载。

## 3. 创建并修改配置

```bash
cp deploy/docker.env.example .env
openssl rand -hex 32   # APP_SECRET_KEY
openssl rand -hex 24   # POSTGRES_PASSWORD
chmod 600 .env
```

### 3.1 必须修改

| 变量 | 要求 |
| --- | --- |
| `APP_SECRET_KEY` | 使用第一条随机值。它用于加密身份源、集成和 Webhook 密钥；启用后不得无备份轮换 |
| `POSTGRES_PASSWORD` | 使用第二条随机值。避免 `@:/?#%` 等 URL 保留字符 |
| `AUTH_PUBLIC_BASE_URL` | 浏览器访问的绝对 HTTPS 根地址，不带路径和结尾 `/` |
| `FRONTEND_URL` | 浏览器前端的公开 Origin，通常与 `AUTH_PUBLIC_BASE_URL` 相同 |

示例：

```dotenv
APP_SECRET_KEY=替换为64位十六进制随机值
POSTGRES_PASSWORD=替换为48位十六进制随机值
AUTH_PUBLIC_BASE_URL=https://agenticops.example.com
FRONTEND_URL=https://agenticops.example.com
```

### 3.2 按接入场景修改

| 场景 | 变量 |
| --- | --- |
| NetBox | `NETBOX_URL`、`NETBOX_API_TOKEN` |
| ELK | `ELK_URL`、`ELK_USERNAME`、`ELK_PASSWORD` |
| Zabbix | `ZABBIX_URL`、`ZABBIX_API_URL`、`ZABBIX_USERNAME`、`ZABBIX_PASSWORD` |
| LLM | `LLM_API_URL`、`LLM_API_KEY`、`LLM_MODEL_NAME` |
| Embedding | `LLM_EMBEDDING_MODEL`、`LLM_EMBEDDING_API_URL`；留空时自动退回关键词检索 |
| 端口 | `BACKEND_PORT`、`FRONTEND_PORT`、`POSTGRES_PORT` |
| 采集容量 | `ELK_INGESTION_PAGE_SIZE`、`ELK_CHECKPOINT_LEASE_SECONDS` |
| Agent Graph | `AGENT_GRAPH_LEASE_SECONDS`、`AGENT_MAX_*`、`HYPOTHESIS_*` |

外部集成也可以在首次登录后从“设置”页面保存；敏感值会使用 `APP_SECRET_KEY` 派生密钥加密。

Agent Graph 的默认预算适合首次 Observe-only 验证：单 Case 最多 16 次 Agent Run、8 次 LLM、12 次工具调用、10 次 Probe、3 次重规划、900 秒运行时间和 3 台目标设备；单 Agent Run 最多 3 次工具调用。不要先放大预算来掩盖无法收敛的诊断。证据确认阈值由 `HYPOTHESIS_CONFIRM_CONFIDENCE`、`HYPOTHESIS_EVIDENCE_MAX_AGE_SECONDS` 和 `HYPOTHESIS_MAX_HIGH_WEIGHT_CONTRADICTIONS` 集中控制。

### 3.3 首次部署必须保持

```dotenv
DEBUG=False
LOG_JSON=True
AUTH_COOKIE_SECURE=True
AUTOMATION_OBSERVE_ONLY=True
WEBHOOK_ALLOW_HTTP=False
```

`AUTH_COOKIE_SECURE=True` 要求用户通过 HTTPS 访问。仅本机临时实验且完全不使用 SSO 时才能设置为 `False`，不能带入生产。

## 4. HTTPS 入口

生产域名应将 `/` 转发到 `${FRONTEND_PORT}`。前端容器会继续把 `/api` 转发到后端，因此同域部署无需向公网单独暴露后端端口。反向代理必须传递 `Host`、`X-Forwarded-For` 和 `X-Forwarded-Proto`。

SSO Provider 中登记的回调地址格式为：

```text
https://agenticops.example.com/api/auth/callback/<provider_key>
```

在 HTTPS 入口工作前不要启用 OIDC/SAML Provider。

## 5. 全新安装

先验证变量展开，输出中不得出现 `change_me` 或 `replace_with`：

```bash
docker compose config -q
if docker compose config | grep -E 'change_me|replace_with'; then
  echo '发现未替换配置，请停止部署'
  exit 1
fi
```

构建并显式迁移数据库：

```bash
docker compose build
docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d backend worker frontend
docker compose ps
```

`migrate` 必须成功退出；应用启动不会偷偷创建或修改 schema。

v0.2.0 的 Alembic head 是 `0011_multi_agent_graph`。确认迁移任务输出无错误，并保留迁移日志；`backend` 和 `worker` 必须使用同一镜像、同一 `DATABASE_URL` 和同一版本配置。

## 6. 已有 AgenticOps 数据库接管

本节只用于尚无 `alembic_version` 表的旧数据库，不能用于全新安装。操作前必须完成 `pg_dump -Fc` 备份并停止旧应用写入。

准备旧库连接串。若旧库由本 Compose 托管，先启动 `postgres`；外部 PostgreSQL 不需要该步骤：

```bash
docker compose up -d postgres
export LEGACY_DATABASE_URL='postgresql://user:password@database-host:5432/netops_agenticops'
docker compose run --rm --no-deps \
  -e DATABASE_URL="$LEGACY_DATABASE_URL" backend \
  python -m scripts.adopt_alembic_baseline \
  --confirm-existing-schema
unset LEGACY_DATABASE_URL
```

脚本会检查活动表和关键列；任何不匹配都会拒绝写入版本标记。数据库已经受 Alembic 管理时只运行 `docker compose run --rm migrate`。

## 7. 创建首个紧急管理员

仅空用户库允许执行一次：

```bash
export BOOTSTRAP_ADMIN_PASSWORD='密码管理器生成的长随机密码'
docker compose exec -e BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" backend \
  python -m scripts.bootstrap_admin \
  --username admin \
  --display-name Administrator \
  --confirm-create-first-admin
unset BOOTSTRAP_ADMIN_PASSWORD
```

该账号用于 SSO 故障恢复，不应作为日常共享账号。登录后访问 `/identity` 配置 OIDC、LDAP/AD 或 SAML，并验证组到角色映射、禁用用户和登出。

## 8. 外部集成初始化

1. `/settings`：配置并测试 NetBox、ELK、Zabbix 和 LLM。
2. SSH 管理：导入设备 host key、绑定凭据与 `probe.read` 权限；不要开放任意命令。
3. `/webhooks`：配置通用 Endpoint、订阅事件和独立密钥。
4. Webhook 接收端必须按原始 body 验证：

```text
signed_bytes = timestamp + "." + event_id + "." + raw_body
X-AgenticOps-Signature = "v1=" + hex(HMAC-SHA256(secret, signed_bytes))
```

同时校验 `X-AgenticOps-Timestamp` 的时效并按 `X-AgenticOps-Event-Id` 幂等。Endpoint 默认必须是解析到公网 IP 的 HTTPS URL；当前版本不支持内网地址白名单。

ELK 代理必须提供唯一 `document_id`，并按 `(timestamp, document_id)` 升序支持 `search_after`。不能保证稳定顺序时采集器会拒绝推进 checkpoint。

## 9. 安装验收

```bash
curl -f http://127.0.0.1:${BACKEND_PORT:-8000}/health/live
curl -f http://127.0.0.1:${BACKEND_PORT:-8000}/health/ready
curl -f http://127.0.0.1:${BACKEND_PORT:-8000}/health/dependencies
curl -f http://127.0.0.1:${BACKEND_PORT:-8000}/metrics
docker compose exec worker python -m scripts.check_worker_health
docker compose logs --tail=100 backend worker
```

还必须通过公开 HTTPS 域名验证登录、CSRF、SSO 回调和前端刷新。`/health/dependencies` 中未启用的集成可以显示 `disabled`，Worker 必须为 `alive`。

### 9.1 v0.2.0 Agent Graph 验收

使用非生产测试 Case 在 Case 详情页点击“运行智能体”，并确认：

1. 接口立即返回 `202 Accepted` 和持久化 `graph_run_id`，页面进入运行中而不是等待整轮诊断。
2. `GET /api/cases/{case_id}/graph-runs/{graph_run_id}` 可看到当前状态与节点。
3. Timeline、Hypotheses 和 Agent Budget 面板来自后端持久化数据，刷新页面后仍可恢复。
4. 停止并重新启动 Worker 后，过期租约由 Worker 恢复，旧 Checkpoint 和 Timeline 不丢失。
5. `AUTOMATION_OBSERVE_ONLY=True` 时 Graph 在 Safety Review 后停止或等待人工，不产生真实设备变更执行记录。

对应查询接口为：

```text
GET /api/cases/{case_id}/graph-runs
GET /api/cases/{case_id}/graph-runs/{graph_run_id}
GET /api/cases/{case_id}/timeline
GET /api/cases/{case_id}/hypotheses
GET /api/cases/{case_id}/agent-budget
```

这些浏览器 API 继续要求 Session、RBAC 和 CSRF；不要为验收临时关闭认证或 PolicyGuard。

## 10. 从旧版本升级到 v0.2.0

升级会新增持久化 Graph、任务、消息、工具调用、预算、Checkpoint、Timeline、状态转换和假设表，并扩展 Case 状态枚举。旧 Case、Evidence、Claim、审批、冻结计划和执行记录仍可读取。升级期间必须停止 API 与 Worker 写入，不能只重启前端。

```bash
export TARGET_RELEASE=v0.2.0
git rev-parse HEAD > pre-upgrade-commit.txt
docker compose stop worker backend
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "netops_agenticops-$(date +%Y%m%d%H%M%S).dump"
git fetch origin --tags --prune
git checkout "$TARGET_RELEASE"
git describe --tags --exact-match
docker compose build
docker compose run --rm migrate
docker compose up -d backend worker frontend
docker compose ps
unset TARGET_RELEASE
```

升级后重复第 9 节全部验收，并检查：

```bash
curl -fsS http://127.0.0.1:${BACKEND_PORT:-8000}/ | grep '0.2.0'
docker compose logs --tail=200 migrate backend worker
```

迁移失败时不要反复重试或继续启动 Worker，应保留数据库、日志、旧提交 SHA 和备份，按 [0011 迁移/回滚说明](./docs/MIGRATION_0011_MULTI_AGENT_GRAPH.md) 与生产运行手册恢复。数据库已产生 v0.2.0 Graph 数据后，优先恢复升级前备份到新库；不要在原生产库上盲目 downgrade。

### 10.1 API 兼容提醒

原路径 `POST /api/cases/{case_id}/run-agents` 保留，但默认从“同步返回诊断结果”变为“返回 `202 Accepted` 和 `graph_run_id`”。旧客户端迁移期可显式使用 `wait=true&timeout_seconds=30`，但等待超时不会取消后台 Graph。前端默认使用轮询，不需要 WebSocket。

### 10.2 回退应用

若迁移成功但尚未产生新 Graph 数据，可在确认 schema 兼容后停止 Worker/API，切回 `pre-upgrade-commit.txt` 记录的提交并重建。若已经产生新数据或无法证明兼容，恢复升级前 `pg_dump -Fc` 到新的空数据库，再切换 `DATABASE_URL`。任何回退都保持 `AUTOMATION_OBSERVE_ONLY=True`，并先启动 API 验证健康后再启动 Worker。

## 11. 停止与卸载

停止服务但保留数据库：

```bash
docker compose down
```

以下命令会永久删除 PostgreSQL 数据卷，只能用于确认不再需要数据的环境：

```bash
docker compose down -v
```

## 12. 下一步

安装完成后仍保持 observe-only。按照 [生产运行手册](./docs/PRODUCTION_DEPLOYMENT.md) 接入监控、完成恢复演练并运行至少 14 天 Shadow Mode，再按低风险命令目录逐项放量。
