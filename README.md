# NetOps Platform

NetOps Platform 是一个面向网络运维场景的全栈系统，覆盖资产视图、运维驾驶舱、事件中心、日志分析、自动化任务、异常类型治理、SSH 凭据与命令模板管理。

## 1. 技术栈

- 前端：Vue 3 + Vite + TypeScript + Pinia + Vue Router
- 后端：FastAPI + SQLAlchemy
- 数据库：PostgreSQL
- 外部集成：NetBox / ELK / LLM / SSH

## 2. 最新项目结构（按当前代码）

```text
netops_bs/
├── backend/
│   ├── api/                          # FastAPI 路由层
│   │   ├── assets.py                 # 资产查询与配置拉取
│   │   ├── events.py                 # 事件中心主链路
│   │   ├── logs.py                   # 日志检索与分析
│   │   ├── automation.py             # 自动化中心
│   │   ├── abnormal_types.py         # 异常类型管理
│   │   ├── ssh_management.py         # SSH 凭据与设备绑定
│   │   ├── command_templates.py      # 命令模板管理
│   │   ├── models.py                 # LLM 模型设置
│   │   ├── chat.py                   # 历史聊天接口（保留）
│   │   ├── sessions.py               # 历史会话接口（保留）
│   │   └── schemas/                  # API Schema 定义
│   ├── services/                     # 业务服务层（规则、执行、采样、反馈）
│   ├── models/                       # SQLAlchemy 模型与提示词
│   ├── mcp/                          # 外部系统访问封装
│   ├── scripts/                      # 初始化/运维/排障脚本
│   ├── config/                       # 配置项
│   └── main.py                       # FastAPI 入口
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard/            # 驾驶舱
│   │   │   ├── Assets.vue            # 资产
│   │   │   ├── Events.vue            # 事件中心
│   │   │   ├── Logs.vue              # 日志
│   │   │   ├── Settings.vue          # 设置
│   │   │   └── automation/           # 自动化子模块
│   │   ├── api/                      # 前端 API 客户端
│   │   ├── components/               # 布局与导航
│   │   ├── router/                   # 路由
│   │   └── store/                    # 状态管理
│   └── package.json
├── docs/
│   ├── EVENTS_MIGRATION_PLAN.md      # 事件迁移方案
│   ├── RUNBOOK.md                    # 运行手册
│   ├── TICKET_INTEGRATION_GUIDE.md   # 工单对接说明
│   └── AUTOMATION_DATABASE_DESIGN.md # 自动化数据库设计
└── README.md
```

## 3. 前端模块说明

### 3.1 一级导航模块

- `/` 驾驶舱（Dashboard）
- `/assets` 资产视图
- `/events` 事件中心（原 `/alerts` 已重定向）
- `/tickets` 本地工单
- `/logs` 日志中心
- `/automation/dashboard` 自动化中心
- `/automation/abnormal-types` 异常类型管理
- `/settings` 系统设置

### 3.2 自动化子模块

- `/automation/samples` 日志采样
- `/automation/tasks` 任务列表
- `/automation/tasks/:id` 任务详情
- `/automation/analysis-results` 研判结果
- `/automation/policies` 策略
- `/automation/audit` 审计
- `/automation/abnormal-types` 异常类型

## 4. 后端模块说明

### 4.1 API 层

- `assets.py`：设备/IP/站点/机柜/VLAN/前缀、配置查看、配置抓取、厂商、同步
- `events.py`：事件接入、事件查询、只读派发、工单创建、关联查询
- `tickets.py`：本地工单列表与状态更新
- `logs.py`：ELK 日志查询、聚合、单条/批量/按设备分析
- `automation.py`：站点开关、样本、分析结果、任务、反馈、仪表盘、手动触发
- `abnormal_types.py`：异常类型 CRUD、状态切换、阈值批量更新、统计
- `ssh_management.py`：凭据管理、NetBox 设备筛选、绑定、连通性测试、命令执行
- `command_templates.py`：命令模板 CRUD、部署校验、模板解析
- `models.py`：LLM 模型设置管理（增删改查、激活、测试、provider 列表）
- `chat.py`、`sessions.py`：历史聊天能力保留接口

### 4.2 服务层（重点）

- `log_sampler.py`：日志采样任务与周期调度
- `automation_orchestrator.py`：自动化编排核心
- `decision_service.py`：决策任务创建与状态流转
- `execution_engine.py`：执行引擎（含 observe-only 安全保护）
- `event_skill_service.py`：事件到只读 skill 的路由
- `ticket_adapter.py`：工单适配器（当前固定 `TICKET_MODE=local`，外部模式仅预留）
- `feedback_learning_service.py`：反馈学习与统计
- `ssh_service.py`：SSH 通道与命令执行

### 4.3 模型层（重点）

`backend/models/automation.py` 包含核心实体：
- `AlertEvent`
- `LocalTicket`
- `AutomationTask`
- `AutomationPolicy`
- `AutomationActionLog`
- `AutomationTaskFeedback`
- 以及 site、sample、analysis 等支撑实体

## 5. API 详细介绍

以下均为后端真实注册路由，基础前缀为 `http://<host>:8000`。

### 5.1 事件中心 API（`/api/events`）

- `GET /api/events/mode`：获取运行模式（`observe_only` 或 `normal`）
- `POST /api/events/ingest`：接入事件（支持去重 upsert）
- `POST /api/events/ingest/splunk`：接入 Splunk Webhook（支持 token 校验）
- `POST /api/events/ingest/eda`：接入 EDA rulebook 事件（可选自动只读派发）
- `GET /api/events`：按状态/级别/来源/站点/设备分页查询事件
- `POST /api/events/{event_id}/dispatch-readonly`：创建只读研判任务（人工确认前置）
- `POST /api/events/{event_id}/playbook-draft-check`：生成并校验 Playbook 草稿（仅 check，不执行配置）
- `POST /api/events/{event_id}/ticket`：创建工单（默认本地工单模块）
- `GET /api/events/{event_id}/relations`：查询事件关联工单与任务

### 5.1.1 本地工单 API（`/api/tickets`）

- `GET /api/tickets`：按状态/事件查询本地工单
- `GET /api/tickets/{ticket_code}`：查询工单详情
- `PATCH /api/tickets/{ticket_code}`：更新工单状态（`open|in_progress|resolved|closed`）

### 5.2 资产 API（`/api/assets`）

- `GET /api/assets/devices`：设备列表
- `GET /api/assets/devices/{device_id}`：设备详情
- `GET /api/assets/devices/with-ip`：带 IP 的设备列表
- `GET /api/assets/devices/{device_id}/config`：设备配置查看
- `POST /api/assets/devices/{device_id}/fetch-config`：拉取并写入设备配置
- `GET /api/assets/ips`：IP 列表
- `GET /api/assets/sites`：站点列表
- `GET /api/assets/racks`：机柜列表
- `GET /api/assets/racks/{rack_id}/devices`：机柜下设备
- `GET /api/assets/vlans`：VLAN 列表
- `GET /api/assets/prefixes`：前缀列表
- `GET /api/assets/prefixes/{prefix_id}/ips`：前缀下 IP
- `GET /api/assets/vendors`：厂商列表
- `POST /api/assets/sync/devices`：同步设备到本地资产镜像
- `POST /api/assets/clear-cache`：清理资产缓存

### 5.3 日志 API（`/api/logs`）

- `GET /api/logs/bases`：日志基础配置列表
- `GET /api/logs/query`：通用查询
- `GET /api/logs/search`：搜索查询
- `GET /api/logs/base/{base_name}`：按基础配置查询
- `GET /api/logs/deyang`：德阳预置查询
- `POST /api/logs/analyze-single`：单条日志分析
- `POST /api/logs/analyze`：批量日志分析
- `POST /api/logs/aggregate`：日志聚合分析
- `POST /api/logs/analyze-device`：设备维度日志分析
- `POST /api/logs/clear-cache`：清理日志缓存

### 5.4 自动化中心 API（`/api/automation`）

- 站点与开关：
- `GET /api/automation/sites`
- `GET /api/automation/sites/{site_id}`
- `PUT /api/automation/sites/{site_id}/automation-toggle`

- 样本与分析：
- `GET /api/automation/samples`
- `GET /api/automation/samples/{sample_id}`
- `GET /api/automation/analysis-results`
- `GET /api/automation/analysis-results/{result_id}`

- 任务与反馈：
- `GET /api/automation/tasks`
- `GET /api/automation/tasks/{task_id}`
- `POST /api/automation/tasks/{task_id}/dispatch-config`
- `GET /api/automation/tasks/{task_id}/feedback`
- `POST /api/automation/tasks/{task_id}/feedback`

- 反馈统计：
- `GET /api/automation/feedback/stats`
- `GET /api/automation/feedback/trends`
- `GET /api/automation/feedback/insights`

- 策略与仪表盘：
- `GET /api/automation/policies`
- `GET /api/automation/policies/{policy_id}`
- `GET /api/automation/dashboard/summary`
- `GET /api/automation/dashboard/hourly-trends`
- `GET /api/automation/dashboard/trends`

- 手动触发：
- `POST /api/automation/trigger-diagnosis`
- `POST /api/automation/trigger-alerts`
- `GET /api/automation/resolve-commands`

### 5.5 异常类型 API（`/api/abnormal-types`）

- `GET /api/abnormal-types/`：列表
- `GET /api/abnormal-types/{type_id}`：详情
- `POST /api/abnormal-types/`：创建
- `PUT /api/abnormal-types/{type_id}`：更新
- `PATCH /api/abnormal-types/{type_id}/status`：状态变更
- `DELETE /api/abnormal-types/{type_id}`：删除
- `POST /api/abnormal-types/batch-update-thresholds`：批量更新阈值
- `GET /api/abnormal-types/stats/summary`：统计摘要

### 5.6 SSH 管理 API（`/api/ssh`）

- `GET /api/ssh/credentials`：凭据列表
- `POST /api/ssh/credentials`：创建凭据
- `PUT /api/ssh/credentials/{credential_id}`：更新凭据
- `DELETE /api/ssh/credentials/{credential_id}`：删除凭据
- `GET /api/ssh/netbox/devices`：查询 NetBox 设备候选
- `POST /api/ssh/credentials/{credential_id}/bind-devices`：绑定设备
- `GET /api/ssh/credentials/{credential_id}/bindings`：查询绑定
- `POST /api/ssh/connectivity-test`：连通性测试
- `POST /api/ssh/execute-commands`：执行命令

### 5.7 命令模板 API（`/api/command-templates`）

- `GET /api/command-templates`：列表
- `POST /api/command-templates`：创建
- `PUT /api/command-templates/{template_id}`：更新
- `DELETE /api/command-templates/{template_id}`：删除
- `POST /api/command-templates/validate-deployment`：部署校验
- `POST /api/command-templates/resolve`：模板解析

### 5.8 模型设置 API（`/api/settings`）

- `GET /api/settings/models`：模型列表
- `GET /api/settings/models/active`：当前激活模型
- `POST /api/settings/models`：创建模型
- `PUT /api/settings/models/{model_id}`：更新模型
- `DELETE /api/settings/models/{model_id}`：删除模型
- `POST /api/settings/models/{model_id}/activate`：激活模型
- `GET /api/settings/models/providers`：Provider 列表
- `GET /api/settings/models/test/{model_id}`：模型连通性测试

### 5.9 历史保留 API

- 聊天：`POST /api/chat/`
- 会话：
- `GET /api/sessions/`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/`
- `DELETE /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/messages`

## 6. 运行方式

### 6.1 后端

```bash
cd backend
pip3 install -r requirements.txt
python3 main.py
```

- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 6.2 前端

```bash
cd frontend
npm install
npm run dev
```

- 默认地址：`http://localhost:5173`

## 7. 开发与发布基线

每次提交至少满足：

```bash
cd backend
python3 -m compileall .

cd ../frontend
npm run build
```

## 8. 当前迁移状态与约束

1. 事件中心已替代旧告警主链路，`/alerts` 前端路由已重定向到 `/events`。
2. 工单接口保持预留（默认 `TICKET_MODE=local`），外部系统暂不接入。
3. 默认运行在 `observe_only=true` 安全模式，阻断非只读动作。
4. 详细迁移与运行细则见：
- `docs/EVENTS_MIGRATION_PLAN.md`
- `docs/RUNBOOK.md`

## 9. API 请求示例（curl）

默认后端地址：

```bash
export BASE_URL="http://localhost:8000"
```

### 9.1 事件中心

查询运行模式：

```bash
curl -s "$BASE_URL/api/events/mode"
```

接入事件：

```bash
curl -s -X POST "$BASE_URL/api/events/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "SPLUNK",
    "event_type": "interface_down",
    "name": "core-sw1 ge-0/0/1 down",
    "severity": "warning",
    "severity_level": 2,
    "host": "10.0.0.10",
    "site_id": 1
  }'
```

查询事件列表：

```bash
curl -s "$BASE_URL/api/events?status=open&limit=20&skip=0"
```

触发只读派发：

```bash
EVENT_ID=1
curl -s -X POST "$BASE_URL/api/events/$EVENT_ID/dispatch-readonly" \
  -H "Content-Type: application/json" \
  -d '{"reviewer":"operator"}'
```

查询事件关联：

```bash
curl -s "$BASE_URL/api/events/$EVENT_ID/relations"
```

创建工单（当前默认本地工单）：

```bash
curl -s -X POST "$BASE_URL/api/events/$EVENT_ID/ticket" \
  -H "Content-Type: application/json" \
  -d '{"priority":"P3","requester":"netops-automation"}'
```

### 9.2 自动化中心

任务列表：

```bash
curl -s "$BASE_URL/api/automation/tasks?limit=20&skip=0"
```

任务详情：

```bash
TASK_ID=1
curl -s "$BASE_URL/api/automation/tasks/$TASK_ID"
```

提交任务反馈：

```bash
curl -s -X POST "$BASE_URL/api/automation/tasks/$TASK_ID/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "verdict": "correct",
    "comment": "处理建议有效",
    "reviewer": "operator",
    "tags": ["event-center", "readonly"]
  }'
```

### 9.3 SSH 管理

创建 SSH 凭据：

```bash
curl -s -X POST "$BASE_URL/api/ssh/credentials" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "core-switch-admin",
    "username": "admin",
    "auth_type": "password",
    "password": "your-password",
    "port": 22
  }'
```

连通性测试：

```bash
curl -s -X POST "$BASE_URL/api/ssh/connectivity-test" \
  -H "Content-Type: application/json" \
  -d '{
    "credential_id": 1,
    "netbox_device_id": 1001
  }'
```

### 9.4 模型设置

查询模型列表：

```bash
curl -s "$BASE_URL/api/settings/models"
```

创建模型：

```bash
curl -s -X POST "$BASE_URL/api/settings/models" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Qwen3-32B-AWQ",
    "provider": "vllm",
    "api_key": "EMPTY_OK_IF_LOCAL",
    "api_url": "http://127.0.0.1:8000/v1",
    "model": "Qwen/Qwen3-32B-AWQ",
    "parameters": {"temperature": 0.7, "max_tokens": 4096}
  }'
```

## 10. 常见错误码与排障对照

### 10.1 HTTP 状态码说明

- `200 OK`：请求成功。
- `400 Bad Request`：参数非法或字段校验失败。
- `404 Not Found`：资源不存在（如事件/任务/模板 id 错误）。
- `422 Unprocessable Entity`：请求体结构不匹配 schema。
- `500 Internal Server Error`：后端内部异常，需看后端日志。

### 10.2 高频错误与处理建议

- 事件派发失败：`Event missing site_id, cannot dispatch task`
- 原因：事件缺失 `site_id`，任务创建前置条件不满足。
- 处理：接入事件时补齐 `site_id`，或完善事件到站点映射。

- observe-only 阻断：`Action blocked in observe-only mode`
- 原因：当前 `automation_observe_only=true` 且动作非 `read_only`。
- 处理：将动作配置设为 `read_only=true`，或仅在受控环境关闭 observe-only。

- 422 请求校验失败
- 原因：JSON 字段名/类型不符合接口 schema。
- 处理：对照 `backend/api/schemas/*.py` 或 `/docs` 中该接口 schema。

- 工单未接真实系统，仅返回本地号
- 现象：`ticket_id` 形如 `LOCAL-*`。
- 原因：当前 `TICKET_MODE=local`，默认本地闭环。
- 处理：后续如需对接外部系统，再按环境切换 `TICKET_MODE=external` 并配置工单参数。

- 前端构建失败（TS 严格模式）
- 原因：历史类型债务或新增字段未同步前端类型定义。
- 处理：优先更新 `frontend/src/api/*.ts` 与页面引用类型，再执行 `npm run build`。
