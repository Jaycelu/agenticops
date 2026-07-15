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
git clone https://github.com/Jaycelu/netops_bs.git
cd netops_bs
git checkout main
```

确认当前提交并记录到变更单：

```bash
git rev-parse HEAD
```

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

外部集成也可以在首次登录后从“设置”页面保存；敏感值会使用 `APP_SECRET_KEY` 派生密钥加密。

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

## 10. 日常升级

```bash
git rev-parse HEAD
docker compose stop worker backend
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "netops_agenticops-$(date +%Y%m%d%H%M%S).dump"
git fetch origin
git checkout main
git pull --ff-only origin main
docker compose build
docker compose run --rm migrate
docker compose up -d backend worker frontend
docker compose ps
```

升级后重复第 9 节验收。迁移失败时不要反复重试或继续启动 Worker，应保留日志并按生产运行手册恢复。

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
