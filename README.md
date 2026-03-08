# NetOps AgenticOps Platform v0.1.1

这是当前版本的真实运行说明。项目主架构已经切换到：

`Event / Case / Multi-Agent / Memory / Fabric`

旧 `automation center`、旧 `streamlit + langchain_agent`、旧异常模板思路都已经退出主运行链。

## 当前模块

前端主模块：

- `Dashboard`
- `Events`
- `Cases`
- `Agents`
- `Memories`
- `Fabric`
- `Logs`
- `Zabbix`
- `Assets`
- `Tickets`
- `Settings`

后端主 API：

- `/api/events`
- `/api/cases`
- `/api/agents`
- `/api/memories`
- `/api/fabric`
- `/api/logs`
- `/api/zabbix`
- `/api/assets`
- `/api/tickets`
- `/api/sites`
- `/api/ssh`
- `/api/command-templates`
- `/api/settings/models`
- `/api/settings/integrations`
- `/api/settings/log-scopes`

说明：

- `/api/automation` 已从主应用路由中下线，不再作为运行态入口。
- `frontend/streamlit` 和 `backend/langchain_agent` 已退役。
- 主前端是 `Vue 3 + Vite`，不是 Streamlit。

## 当前主链路

1. `ELK / Zabbix / 外部事件` 进入 `Event Center`
2. 统一写入 `SourceEvent`
3. 由事件分流逻辑决定是否进入 `Case`
4. `Case Orchestrator` 驱动 4 个智能体
5. 输出 `Evidence / Agent Claims / RemediationPlan / ExecutionRun / MemoryEntry`
6. 必要时进入 `Tickets`

四个智能体：

- `Alert Triage Agent`
- `Historical Analysis Agent`
- `Insight Analysis Agent`
- `Autonomous Remediation Agent`

## 环境要求

- Python `3.11+`
- Node.js `18+`
- PostgreSQL `14+`
- 可访问的 `NetBox / ELK / Zabbix / LLM`

说明：

- 数据库只支持 `PostgreSQL`
- 不支持 `SQLite`
- 数据库不通时，`/health` 会返回 `503`

## 项目结构

```text
netops_bs/
├── backend/
│   ├── adapters/
│   ├── agents/
│   ├── api/
│   ├── compat/
│   ├── config/
│   ├── engines/
│   ├── models/
│   ├── scripts/
│   ├── services/
│   ├── database.py
│   └── main.py
├── frontend/
│   ├── src/
│   └── package.json
├── docs/
└── README.md
```

## PostgreSQL 使用说明

### 1. 当前主表

当前版本启动时只会自动创建这些主运行表：

- `site`
- `site_automation_switch`
- `device_state`
- `log_sample`
- `log_analysis_result`
- `automation_policy`
- `raw_anomaly`
- `ssh_credential`
- `ssh_credential_device_binding`
- `asset_device`
- `local_ticket`
- `command_template`
- `source_event`
- `case_record`
- `evidence_item`
- `agent_run`
- `agent_claim`
- `memory_entry`
- `remediation_plan`
- `execution_run`
- `integration_setting`
- `log_scope`

说明：

- `local_ticket` 现在以 `source_event_id` 为主关联键
- 启动时会自动补齐 `local_ticket.source_event_id`
- 启动时会自动删除 `local_ticket -> alert_event` 的旧外键依赖

对应逻辑见：

- [database.py](/Users/jayce/Desktop/Jayce/netops_bs/backend/database.py)

### 2. 已退场的旧表

这些旧表不再参与主应用运行：

- `alert_event`
- `automation_task`
- `automation_action_log`
- `automation_approval`
- `automation_task_feedback`

说明：

- 主应用不会再自动创建这些旧表
- 主运行链不再查询这些旧表
- 它们只用于一次性补迁和离线归档

### 3. 新装数据库

Ubuntu / Debian：

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

macOS Homebrew：

```bash
brew install postgresql@16
brew services start postgresql@16
```

检查服务：

```bash
pg_isready
```

### 4. 创建用户和数据库

推荐：

```bash
createuser -P netops
createdb -O netops netops_agenticops
```

验证连接：

```bash
psql postgresql://netops:<your_password>@127.0.0.1:5432/netops_agenticops -c "select 1;"
```

如果这里失败，不要继续启动前后端。

### 5. 后端数据库配置

复制模板：

```bash
cp backend/.env.example backend/.env
```

至少确认：

```env
APP_SECRET_KEY=replace_with_a_long_random_secret
DATABASE_URL=postgresql://netops:<your_password>@127.0.0.1:5432/netops_agenticops
AUTOMATION_DATABASE_URL=
LLM_API_URL=http://<your-llm-host>/v1
LLM_API_KEY=<your-llm-key>
LLM_MODEL_NAME=Qwen/Qwen3-32B-AWQ
FRONTEND_URL=http://localhost:5173
```

说明：

- `AUTOMATION_DATABASE_URL` 留空时会回退到 `DATABASE_URL`
- 当前推荐直接用同一个 PostgreSQL 库

## 旧表补迁和退场

### 1. 先做补迁

如果你的库里还有历史 `AutomationTask / AutomationTaskFeedback`，先跑补迁：

```bash
python3 backend/scripts/backfill_agenticops_data.py --dry-run --limit 100
python3 backend/scripts/backfill_agenticops_data.py --limit 1000
```

这个脚本会把旧任务数据补到：

- `source_event`
- `case_record`
- `remediation_plan`
- `memory_entry`

### 2. 再做旧表退场

先 dry-run：

```bash
python3 backend/scripts/retire_legacy_schema.py --dry-run
```

确认无误后归档退场：

```bash
python3 backend/scripts/retire_legacy_schema.py
```

如果你确定要物理删除旧表：

```bash
python3 backend/scripts/retire_legacy_schema.py --drop
```

说明：

- 默认会先补迁，再把旧表重命名成 `archived__*`
- `--drop` 会直接删除旧表
- 脚本可以重复执行，已处理“旧表不存在”的情况

对应脚本：

- [backfill_agenticops_data.py](/Users/jayce/Desktop/Jayce/netops_bs/backend/scripts/backfill_agenticops_data.py)
- [retire_legacy_schema.py](/Users/jayce/Desktop/Jayce/netops_bs/backend/scripts/retire_legacy_schema.py)

## 完整启动说明

### 方式 A：开发/自测启动

#### 1. 启动后端

```bash
cd /path/to/netops_bs
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### 2. 启动前端

另开一个终端：

```bash
cd /path/to/netops_bs/frontend
npm install
cp .env.example .env
npm run dev -- --host 0.0.0.0 --port 5173
```

访问：

- `http://127.0.0.1:5173`
- `http://127.0.0.1:8000/docs`

### 方式 B：脚本一键启动

```bash
cd /path/to/netops_bs
./start_all.sh
```

说明：

- `start_all.sh` 现在会启动 `FastAPI + Vue`
- 日志文件：
  - `logs/backend.log`
  - `logs/frontend.log`

### 方式 C：systemd / 服务方式

前端服务文件：

- [netops-frontend.service](/Users/jayce/Desktop/Jayce/netops_bs/netops-frontend.service)

如果你用 systemd，推荐：

```bash
sudo systemctl daemon-reload
sudo systemctl restart netops-backend
sudo systemctl restart netops-frontend
sudo systemctl status netops-backend
sudo systemctl status netops-frontend
```

## 完全重启整套服务

### 开发/脚本环境

停止：

```bash
cd /path/to/netops_bs
./manage_services.sh
```

或者直接杀掉端口进程：

```bash
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
```

重新启动：

```bash
cd /path/to/netops_bs
./start_all.sh
```

### systemd 环境

```bash
sudo systemctl restart postgresql
sudo systemctl restart netops-backend
sudo systemctl restart netops-frontend
```

查看日志：

```bash
tail -f /opt/netops/logs/backend.log
tail -f /opt/netops/logs/frontend.log
```

## 首次启动后的配置顺序

1. 打开 `Settings -> 集成配置`
2. 配置 `NetBox`
3. 配置 `ELK`
4. 配置 `Zabbix`
5. 分别点击“测试连接”
6. 配置至少一个 `日志范围`
7. 测试日志范围查询

说明：

- 敏感字段会加密存库，不会明文回显
- 如果没有配置日志范围，日志采样和日志页会表现异常或为空

## 启动后的验收顺序

### 1. 先看健康检查

```bash
curl http://127.0.0.1:8000/health
```

期望：

- HTTP `200`
- `status=healthy`
- `checks.database.status=healthy`

如果是 `503`，先修数据库，不要继续联调前端。

### 2. 再做接口烟雾检查

```bash
curl http://127.0.0.1:8000/api/agents/catalog
curl http://127.0.0.1:8000/api/agents/health
curl http://127.0.0.1:8000/api/cases/overview
curl http://127.0.0.1:8000/api/memories/overview
curl http://127.0.0.1:8000/api/fabric/overview
curl http://127.0.0.1:8000/api/logs/scopes
curl http://127.0.0.1:8000/api/assets/sites
```

说明：

- `/api/agents/catalog` 应固定返回 4 个智能体
- `/api/agents/health` 即使还没有运行记录，也应返回 4 个智能体，计数为 `0`

### 3. 最后看前端页面

按这个顺序看：

1. `Dashboard`
2. `Agents`
3. `Cases`
4. `Memories`
5. `Fabric`
6. `Logs`
7. `Events`
8. `Zabbix`

不要把“Dashboard 能打开”当成系统正常的唯一标准。

## 常见问题

### 1. `/health` 返回 503

通常是：

- PostgreSQL 没启动
- `DATABASE_URL` 配错
- 数据库账号密码不对

### 2. 前端能打开但业务页数据不正常

优先检查：

- `/health`
- `DATABASE_URL`
- `/api/cases/overview`
- `/api/fabric/overview`

这类问题通常不是前端单点问题。

### 3. 事件页正常但旧 automation 页访问不到

这是预期行为。

- `/api/automation` 已退出主运行态
- 前端 `/automation/*` 只保留重定向，不再是主业务入口

### 4. 退场脚本执行失败

先确认：

```bash
pg_isready
psql <your_database_url> -c "select 1;"
```

如果数据库本身不可达，任何补迁和退场脚本都会失败。

## 相关文件

- [database.py](/Users/jayce/Desktop/Jayce/netops_bs/backend/database.py)
- [main.py](/Users/jayce/Desktop/Jayce/netops_bs/backend/main.py)
- [start_all.sh](/Users/jayce/Desktop/Jayce/netops_bs/start_all.sh)
- [manage_services.sh](/Users/jayce/Desktop/Jayce/netops_bs/manage_services.sh)
- [retire_legacy_schema.py](/Users/jayce/Desktop/Jayce/netops_bs/backend/scripts/retire_legacy_schema.py)
- [backfill_agenticops_data.py](/Users/jayce/Desktop/Jayce/netops_bs/backend/scripts/backfill_agenticops_data.py)
