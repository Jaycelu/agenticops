# NetOps AgenticOps Platform

这是一个围绕网络运维场景重构后的 AgenticOps 平台。当前主架构已经切换到 `Case + Multi-Agent + Memory + Fabric`，不再以“异常类型/模板”和旧聊天式 agent 为核心。

## 当前架构

平台按四层组织：

1. 数据源层
   - ELK 日志
   - Zabbix 告警
   - NetBox 资产与拓扑
   - SSH 现场取证

2. 分析引擎层
   - `Case Orchestrator`
   - `Alert Triage Agent`
   - `Historical Analysis Agent`
   - `Insight Analysis Agent`
   - `Autonomous Remediation Agent`

3. 记忆系统
   - `episode memory`
   - `pattern memory`
   - `outcome memory`
   - `feedback memory`

4. 输出层
   - `Case Center`
   - `Agent Center`
   - `Memory Center`
   - `Automation Fabric`

核心原则：

- 所有诊断结论都要落到 `case/evidence/claim/plan`。
- Agent 不能直接“编数据”，只能基于结构化证据推理。
- 自动化动作必须经过 `RemediationPlan + Safety Gate + Execution/Audit`。

## 当前模块

前端主模块：

- `Dashboard` 驾驶舱
- `Cases` Case 中心
- `Agents` 智能体中心
- `Memories` 记忆中心
- `Fabric` 自动化执行中心
- `Events` 事件中心
- `Logs` 日志中心
- `Assets` 资产与拓扑
- `Tickets` 工单
- `Settings` 设置

后端主 API：

- `/api/cases`
- `/api/agents`
- `/api/memories`
- `/api/fabric`
- `/api/events`
- `/api/logs`
- `/api/assets`
- `/api/tickets`
- `/api/ssh`
- `/api/command-templates`
- `/api/settings/models`
- `/api/settings/integrations`
- `/api/settings/log-scopes`

说明：

- `/api/automation` 仍保留为迁移兼容层，但已经不是主工作流入口。
- 旧 `abnormal-types`、旧 chat/session agent、旧异常模板模块已经下线。

## 项目结构

```text
netops_bs/
├── backend/
│   ├── adapters/              # ELK / Zabbix / NetBox / SSH 适配层
│   ├── agents/                # 4 个运维智能体
│   ├── api/                   # FastAPI 路由
│   ├── config/                # 配置
│   ├── engines/               # Case orchestrator
│   ├── models/                # legacy + agenticops ORM
│   ├── scripts/               # 初始化/补迁/运维脚本
│   ├── services/              # 兼容服务与基础能力
│   ├── database.py
│   └── main.py
├── frontend/
│   ├── src/api/
│   ├── src/components/
│   ├── src/pages/
│   ├── src/router/
│   └── package.json
├── docs/
│   └── plans/
└── README.md
```

## 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- 可访问 NetBox / ELK / LLM 服务

## 快速启动

### 1. 准备数据库

先启动 PostgreSQL，并创建数据库。

示例：

```bash
createdb netops_agenticops
```

如果你打算直接复用一个已有数据库，也可以，只要 `DATABASE_URL` 指向 PostgreSQL 即可。

### 2. 配置后端环境变量

复制环境模板：

```bash
cp backend/.env.example backend/.env
```

然后按你的服务器环境修改 `backend/.env`。

至少需要确认这些变量：

- `APP_SECRET_KEY`，用于加密 NetBox/ELK/Zabbix 敏感配置和 SSH 凭据
- `DATABASE_URL`
- `AUTOMATION_DATABASE_URL`，可留空，留空时回退到 `DATABASE_URL`
- `LLM_API_URL`
- `LLM_API_KEY`
- `LLM_MODEL_NAME`

NetBox / ELK / Zabbix 建议在系统启动后进入 `设置 -> 集成配置` 页面录入，不再要求写入仓库或 `.env`。

### 3. 启动后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

期望返回：

```json
{"status":"healthy"}
```

### 3.1 启动后先配置集成

后端启动成功后，打开前端的 `设置 -> 集成配置`，录入：

- `NetBox URL + API Token`
- `ELK API URL + 用户名 + 密码`
- `Zabbix URL/API URL + 用户名 + 密码`

这些敏感字段会被加密存入数据库，设置页不会明文回显。

### 3.2 配置日志范围

在 `设置 -> 集成配置 -> 日志范围配置` 中维护 ELK 日志范围：

- `scope_key`：范围唯一标识
- `display_name`：显示名称
- `NetBox Site`：可选绑定
- `aliases`：兼容旧基地名、缩写、站点别名
- `query_filter`：ELK 查询条件
- `default_time_range`：默认时间窗

说明：

- 日志页现在优先按 `日志范围` 查询，而不是硬编码基地列表。
- 采样任务会优先根据绑定的 `site_code / site_name / alias` 解析到日志范围。
- 如果没有绑定范围，采样会记录为未映射，不再默认猜测。

### 4. 配置前端环境变量

复制模板：

```bash
cp frontend/.env.example frontend/.env
```

开发环境默认可用：

- `VITE_API_BASE_URL=/api`

如果你前后端不是同机同端口反向代理，改成：

```bash
VITE_API_BASE_URL=http://<your-server>:8000/api
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

浏览器访问：

- `http://127.0.0.1:5173`

## 服务器快速启动

如果你是在服务器上直接自测，最短路径是：

```bash
cd /path/to/netops_bs
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
$EDITOR backend/.env
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

另开一个终端：

```bash
cd /path/to/netops_bs/frontend
npm install
cp .env.example .env
npm run dev -- --host 0.0.0.0 --port 5173
```

## 服务器联调准备清单

上线前建议按下面顺序逐项确认。

### 1. 基础环境

- PostgreSQL 已启动，`DATABASE_URL` 指向可连接实例
- `APP_SECRET_KEY` 已配置，且不是默认占位值
- 服务器可访问：
  - NetBox
  - ELK
  - Zabbix
  - LLM 服务
- 前端访问地址已加入后端 CORS，或 `FRONTEND_URL` 已配置为实际地址

快速检查：

```bash
pg_isready
curl http://127.0.0.1:8000/health
```

### 2. 后端启动前

- 已执行：

```bash
cp backend/.env.example backend/.env
```

- 已确认以下变量：
  - `APP_SECRET_KEY`
  - `DATABASE_URL`
  - `AUTOMATION_DATABASE_URL`
  - `LLM_API_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL_NAME`

- 如使用反向代理，已确认：
  - `/api` 转发到 `http://127.0.0.1:8000`
  - 前端静态资源可正常访问

### 3. 首次启动后必做配置

打开前端 `设置 -> 集成配置`，依次完成：

1. 配置 `NetBox`
2. 配置 `ELK`
3. 配置 `Zabbix`
4. 点击各自的“测试连接”
5. 配置至少一个“日志范围”
6. 点击“日志范围”的“测试查询”

如果你已有整理好的日志范围 JSON，可以直接导入：

```bash
python3 backend/scripts/import_log_scopes.py /path/to/log_scopes.json --replace
```

### 4. 联调验证顺序

建议按下面顺序验证，不要一开始就直接跑全链路。

1. 访问后端健康检查：

```bash
curl http://127.0.0.1:8000/health
```

2. 验证前端是否能打开：
   - Dashboard
   - Cases
   - Logs
   - Settings

3. 验证只读接口：

```bash
curl http://127.0.0.1:8000/api/logs/scopes
curl http://127.0.0.1:8000/api/assets/sites
curl http://127.0.0.1:8000/api/cases/overview
curl http://127.0.0.1:8000/api/fabric/overview
```

4. 在日志页选择一个“日志范围”，确认能查到日志

5. 触发一次日志聚合或设备分析，确认是否能生成 `Case`

6. 进入 Case 中心，确认以下数据是否完整：
   - evidence
   - agent claims
   - remediation draft

### 5. 重点检查项

- `Settings -> 集成配置` 中不应回显明文密码或 token
- 日志页应显示“日志范围”，而不是依赖内置基地列表
- 如果某个 Site 没绑定日志范围，采样应记录未映射，而不是错误匹配到别的范围
- SSH 凭据新增后应可正常加密保存
- Case 生成后应能看到多 Agent 输出，而不是旧自动化任务逻辑

### 6. 常见阻塞点

- PostgreSQL 未启动
  - 现象：后端启动或 backfill/import 脚本报 `connection refused`
- `APP_SECRET_KEY` 未配置
  - 现象：保存集成配置或 SSH 凭据时报加密相关错误
- ELK URL 正确但过滤条件无结果
  - 现象：测试连接成功，但日志范围测试返回 0 条
- NetBox Site 与日志范围未建立映射
  - 现象：日志采样出现未映射范围

### 7. 联调完成标准

满足以下条件，可以认为服务器联调基本完成：

- 后端和前端都能稳定启动
- NetBox / ELK / Zabbix 测试连接都成功
- 至少一个日志范围测试查询成功
- 日志页能按范围查询日志
- 至少成功生成 1 个 Case
- Case 中能看到 evidence、agent、plan
- README 中的快速启动步骤在当前服务器可复现

## 生产构建

后端：

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run build
npm run preview -- --host 0.0.0.0 --port 4173
```

更常见的做法是把 `frontend/dist` 放到 Nginx，然后将 `/api` 反代到 `http://127.0.0.1:8000`。

## 启动后建议先检查

1. `GET /health` 是否正常
2. 前端 `Settings -> 集成配置` 能否保存并测试连接
3. `GET /api/cases/overview` 是否返回数据
4. `GET /api/fabric/overview` 是否返回数据
5. 前端是否能打开 `Dashboard / Cases / Agents / Memories / Fabric`

## 历史数据补迁

如果你需要把旧 `AutomationTask / AutomationTaskFeedback` 回填到新模型：

```bash
python3 backend/scripts/backfill_agenticops_data.py --dry-run --limit 100
python3 backend/scripts/backfill_agenticops_data.py --limit 1000
```

这个脚本会把历史数据补到：

- `source_event`
- `case_record`
- `remediation_plan`
- `memory_entry`

如果你已经整理好了日志范围 JSON，也可以直接导入：

```bash
python3 backend/scripts/import_log_scopes.py /path/to/log_scopes.json
python3 backend/scripts/import_log_scopes.py /path/to/log_scopes.json --replace
```

JSON 格式支持：

```json
{
  "scopes": [
    {
      "scope_key": "campus_a",
      "display_name": "A 园区日志",
      "netbox_site_id": 12,
      "site_code_snapshot": "CAMPUS_A",
      "site_name_snapshot": "A 园区",
      "aliases": ["campus-a", "园区A"],
      "query_filter": "hostname:10.0.* AND tag:syslog",
      "default_time_range": "-1d,now",
      "enabled": true,
      "sort_order": 10
    }
  ]
}
```

注意：

- 执行前必须先启动 PostgreSQL。
- 当前仓库不会自动启动数据库服务。

## 迁移兼容说明

当前仍保留少量 legacy 模块，仅用于迁移和兼容：

- `models.automation` 中的旧任务/反馈/审批表
- `/api/automation` 的兼容接口
- 部分 retention 和 backfill 脚本

但新的主链路已经固定为：

`events/logs -> case intake -> multi-agent pipeline -> memory/fabric`

## 已完成的关键重构

- 删除异常类型/模板主流程
- 删除旧聊天式 agent
- 日志采样改为 `signal/pattern/case` 语义
- 事件中心与日志中心收敛到 `Case 中心`
- 引入 `Case Orchestrator + 4 Agents`
- 引入 `Memory / Fabric`
- 顶部导航改为左侧导航
- 增加历史 backfill 脚本

## 当前已验证

- `python3 -m compileall backend`
- `npm --prefix frontend run build`

说明：

- `backfill_agenticops_data.py` 的真实 dry-run 还依赖你本地或服务器上的 PostgreSQL 正常启动。
