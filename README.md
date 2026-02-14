# NetOps AI Platform

> 面向园区网络运维的 AI 驱动统一自动化平台
>
> 当前仓库正式运行模式为：`frontend/`（Vue 3 + Vite）+ `backend/`（FastAPI）。
> `frontend/streamlit/` 为历史原型目录，不在当前正式启动流程内。

## 项目概述

NetOps AI Platform 是一个基于 AI 技术的网络运维自动化平台，通过对话式交互和自动化任务调度，帮助网络运维工程师快速定位问题、执行自动化任务、减少手工操作。

### 核心特性

- **AI 对话调度**：通过自然语言对话，AI 自动识别意图、调度工具、执行任务
- **低置信度澄清机制**：意图识别支持 `confidence + missing_slots`，在高风险或信息缺失时先追问，减少误操作
- **统一资产管理**：集成 NetBox，提供设备、IP、站点、机柜等资产管理
- **智能告警分析**：集成 Zabbix，提供告警查询、趋势分析和健康评分
- **日志分析**：集成 ELK，支持 AI 自动生成查询语句和日志聚合分析
- **执行轨迹可视化**：所有 AI 行为可回溯、可审计、可追溯
- **自动化反馈闭环**：支持任务级人工反馈（正确/误判/部分正确）与统计看板
- **反馈学习校准**：研判前按近7/30天反馈动态校准置信度与人工确认策略

## 项目架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Web 前端                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 运维工作台│  │ 资产视图  │  │ 告警中心  │  │ 日志分析  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│  ┌──────────┐                                                   │
│  │ 系统设置  │                                                   │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    AI 调度层（Agent Orchestrator）            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 意图识别      │  │ 执行计划生成  │  │ 执行控制      │      │
│  │ IntentAgent  │  │ PlannerAgent │  │ ExecutorAgent│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐                                               │
│  │ 结果总结      │                                               │
│  │ Summarizer   │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                        工具层（MCP）                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │ NetBox   │  │ Zabbix   │  │ ELK      │                    │
│  │ MCP      │  │ MCP      │  │ MCP      │                    │
│  └──────────┘  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    外部系统                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │ NetBox   │  │ Zabbix   │  │ ELK      │                    │
│  └──────────┘  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端

- **框架**: FastAPI 0.104.1
- **Python**: 3.10+
- **数据库**: SQLAlchemy 2.0.23
- **HTTP 客户端**: httpx 0.25.2, aiohttp 3.9.1
- **NetBox 客户端**: pynetbox 7.5.0
- **Zabbix 客户端**: pyzabbix 1.3.0
- **LLM 客户端**: OpenAI 1.3.7
- **任务调度**: APScheduler 3.10.4
- **日志**: Loguru 0.7.2

### 前端

- **框架**: Vue 3.3.8
- **路由**: Vue Router 4.2.5
- **状态管理**: Pinia 2.1.7
- **UI 组件**: Tailwind CSS 4.1.18
- **图标**: Lucide Vue Next 0.562.0
- **HTTP 客户端**: Axios 1.6.2
- **构建工具**: Vite 5.0.2
- **TypeScript**: 5.3.2

## 项目结构

```
netops/
├── backend/                    # 后端服务
│   ├── agent/                 # AI Agent 模块
│   │   ├── executor.py       # 执行代理
│   │   ├── intent.py         # 意图识别
│   │   ├── orchestrator.py   # 编排器
│   │   ├── planner.py        # 计划生成
│   │   ├── schemas.py        # 数据模型
│   │   └── summarizer.py     # 结果总结
│   ├── api/                  # REST API
│   │   ├── alerts.py         # 告警 API
│   │   ├── assets.py         # 资产 API
│   │   ├── chat.py           # 对话 API
│   │   ├── logs.py           # 日志 API
│   │   ├── models.py         # 模型 API
│   │   ├── sessions.py       # 会话 API
│   │   └── schemas/          # API 请求/响应模型（schema层）
│   ├── config/               # 配置
│   │   ├── logging.py        # 日志配置
│   │   └── settings.py       # 应用设置
│   ├── mcp/                  # MCP 工具封装
│   │   ├── base.py           # 基础 MCP
│   │   ├── netbox_mcp.py     # NetBox MCP
│   │   ├── zabbix_mcp.py     # Zabbix MCP
│   │   └── elk_mcp.py        # ELK MCP
│   ├── models/               # LLM 接口
│   │   ├── llm_client.py     # LLM 客户端
│   │   └── prompts/          # Prompt 模板
│   ├── services/             # 业务服务
│   │   ├── log_analyzer.py   # 日志分析服务
│   │   ├── abnormal_tracker.py          # 异常跟踪（数据库持久化）
│   │   └── feedback_learning_service.py # 反馈学习与风险校准
│   ├── storage/              # 存储模块
│   │   ├── chat_history/     # 聊天历史
│   │   └── session_storage.py
│   ├── utils/                # 工具函数
│   │   ├── cache.py          # 缓存
│   │   └── idgen.py          # ID 生成
│   ├── logs/                 # 日志文件
│   ├── main.py               # 应用入口
│   ├── requirements.txt      # Python 依赖
│   └── .env                  # 环境变量
├── frontend/                 # 前端应用
│   ├── src/
│   │   ├── api/              # API 封装
│   │   │   ├── alerts.ts
│   │   │   ├── assets.ts
│   │   │   ├── chat.ts
│   │   │   ├── logs.ts
│   │   │   ├── sessions.ts
│   │   │   └── settings.ts
│   │   ├── components/       # 组件
│   │   │   └── TopNav.vue    # 顶部导航
│   │   ├── pages/            # 页面
│   │   │   ├── Dashboard.vue # 运维工作台
│   │   │   ├── Assets.vue    # 资产视图
│   │   │   ├── Alerts.vue    # 告警中心
│   │   │   ├── Logs.vue      # 日志分析
│   │   │   ├── Settings.vue  # 系统设置
│   │   │   └── automation/FeedbackStats.vue # 自动化反馈统计详情
│   │   ├── router/           # 路由
│   │   │   └── index.ts
│   │   ├── store/            # 状态管理
│   │   │   └── chat.ts
│   │   ├── App.vue           # 根组件
│   │   ├── main.ts           # 应用入口
│   │   └── style.css         # 全局样式
│   ├── package.json          # Node 依赖
│   ├── vite.config.ts        # Vite 配置
│   ├── tailwind.config.js    # Tailwind 配置
│   └── tsconfig.json         # TypeScript 配置
├── storage/                  # 数据存储
│   ├── alert_linkage/        # 告警联动
│   ├── backups/              # 备份文件
│   │   └── metadata/         # 备份元数据
│   ├── health_reports/       # 健康度报告
│   ├── reports/              # 巡检报告
│   ├── schedules/            # 定时任务
│   ├── inspection_templates.json  # 巡检模板
│   └── INSPECTION_TEMPLATES_README.md
├── deploy/                   # 部署文件
│   ├── env.example           # 环境变量模板
│   └── start.sh              # 启动脚本
├── scripts/                  # 脚本
│   └── monitor-services.sh   # 服务监控
├── docs/                     # 文档
├── DEPLOYMENT.md             # 部署文档
├── PRD.md                    # 产品需求文档
├── netops-backend.service    # 后端服务配置
└── netops-frontend.service   # 前端服务配置
```

## 快速开始

### 启动模式说明（统一）

- 正式开发模式：Vue 前端 `http://localhost:5173` + FastAPI 后端 `http://localhost:8000`
- 不使用模式：`frontend/streamlit/`（历史原型）
- 为避免误启动旧模式，不要使用 `start_all.sh`、`start_streamlit.sh`

## 反馈闭环接口（新增）

- `POST /api/automation/tasks/{task_id}/feedback`：提交人工反馈（correct/incorrect/partial）
- `GET /api/automation/feedback/stats`：按诊断类型统计反馈（支持 `window_days`、`min_samples`）
- `GET /api/automation/feedback/trends`：按诊断类型输出日期趋势
- `GET /api/automation/feedback/insights`：输出误判 TopN 和阈值调整建议
- 前端 `自动化中心 -> 反馈统计`：支持按诊断类型切换、正确率/误判率双线切换、7/30天与自定义日期范围、CSV 导出（含 TopN 建议）

### 环境要求

- Python 3.10+
- Node.js 16+
- NetBox（已配置）
- Zabbix（已配置）
- ELK（已配置）
- 本地大模型 API（已配置）

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd netops
   ```

2. **配置环境变量**
   ```bash
   cp deploy/env.example backend/.env
   vi backend/.env
   ```

   需要配置的参数：
   - `NETBOX_URL`: NetBox 地址
   - `NETBOX_API_TOKEN`: NetBox API Token
   - `ZABBIX_URL`: Zabbix 地址
   - `ZABBIX_API_URL`: Zabbix API URL
   - `ZABBIX_USERNAME`: Zabbix 用户名
   - `ZABBIX_PASSWORD`: Zabbix 密码
   - `LLM_API_URL`: 本地大模型 API 地址
   - `LLM_MODEL_NAME`: 模型名称

3. **启动后端服务**
   ```bash
   cd deploy
   ./start.sh
   ```

   或手动启动：
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 main.py
   ```

   后端服务将在 `http://localhost:8000` 启动

4. **启动前端服务**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   前端服务将在 `http://localhost:5173` 启动

5. **访问页面**
   - 前端首页：`http://localhost:5173`
   - 运维工作台：`http://localhost:5173/dashboard`

### 推荐启动方式（双终端）

终端 A（后端）：
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

终端 B（前端）：
```bash
cd frontend
npm install
npm run dev
```

### 健康检查

```bash
curl http://localhost:8000/health
```

### API 文档

启动后端服务后，访问 `http://localhost:8000/docs` 查看交互式 API 文档

## 已实现功能

### Phase 1: 基础功能（已完成）

#### 后端 API

- **资产管理 API** (`/api/assets`)
  - 设备查询：`GET /api/assets/devices`
  - 设备详情：`GET /api/assets/devices/{id}`
  - 设备配置：`GET /api/assets/devices/{id}/config`
  - IP 查询：`GET /api/assets/ips`
  - 站点查询：`GET /api/assets/sites`
  - 机柜查询：`GET /api/assets/racks`
  - VLAN 查询：`GET /api/assets/vlans`
  - 带有 IP 的设备：`GET /api/assets/devices/with-ip`

- **告警 API** (`/api/alerts`)
  - 告警查询：`GET /api/alerts`
  - 告警详情：`GET /api/alerts/{id}`

- **日志 API** (`/api/logs`)
  - 日志查询：`GET /api/logs`
  - 日志分析：`POST /api/logs/analyze`

- **对话 API** (`/api/chat`)
  - 对话交互：`POST /api/chat`
  - 会话管理：`GET /api/sessions`

- **模型 API** (`/api/models`)
  - 模型列表：`GET /api/models`

#### 前端页面

- **运维工作台** (`/dashboard`)
  - 三栏布局：会话列表、对话区、执行轨迹
  - AI 对话交互
  - 执行步骤可视化
  - 会话历史管理

- **资产视图** (`/assets`)
  - 设备列表查询
  - 设备详情查看
  - 设备配置查看
  - 设备标签显示（stack-master、stack-member）
  - 机柜详情查看
  - 站点、VLAN 查询
  - 设备配置获取

- **告警中心** (`/alerts`)
  - 告警列表
  - 告警详情
  - 告警趋势

- **日志分析** (`/logs`)
  - 日志查询
  - 日志分析

- **系统设置** (`/settings`)
  - 系统配置
  - 巡检模板配置

#### AI Agent 功能

- **意图识别**：自动识别用户查询意图（查询、巡检、分析等）
- **执行计划生成**：根据意图生成执行步骤
- **执行控制**：调度 MCP 工具执行任务
- **结果总结**：汇总执行结果，生成自然语言回复

#### MCP 工具

- **NetBox MCP**：设备、IP、站点、机柜、VLAN 查询
- **Zabbix MCP**：告警查询、指标查询
- **ELK MCP**：日志查询、日志分析

#### 存储功能

- **巡检模板**：预定义核心交换机、汇聚交换机、接入交换机、无线控制器、防火墙巡检模板
- **巡检报告**：存储巡检执行结果
- **备份元数据**：存储配置备份信息
- **告警联动**：存储告警联动规则
- **定时任务**：存储定时任务配置

### 已移除功能（待重构）

- **自动化任务模块**：配置备份、网络巡检、健康度检查
  - 原因：原实现存在架构问题，需要重新设计
  - 计划：在 Phase 2 中重新实现

## API 端点列表

### 资产管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/assets/devices` | 查询设备列表 |
| GET | `/api/assets/devices/with-ip` | 查询有 IP 的设备 |
| GET | `/api/assets/ips` | 查询 IP 地址 |
| GET | `/api/assets/sites` | 查询站点 |
| GET | `/api/assets/racks` | 查询机柜 |
| GET | `/api/assets/vlans` | 查询 VLAN |

### 告警管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/alerts` | 查询告警列表 |
| GET | `/api/alerts/{id}` | 查询告警详情 |

### 日志管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/logs` | 查询日志 |
| POST | `/api/logs/analyze` | 分析日志 |

### 对话管理

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送对话消息 |
| GET | `/api/sessions` | 查询会话列表 |
| GET | `/api/sessions/{id}` | 查询会话详情 |

### 模型管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/models` | 查询可用模型 |

### 系统管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | API 信息 |

## 数据统计

根据当前环境数据：

- **设备总数**: 273 台（带 IP 地址）
- **机柜总数**: 138 个
- **VLAN 总数**: 214 个
- **巡检报告**: 7 份（2026-01-11 至 2026-01-12）
- **巡检模板**: 5 个（核心交换机、汇聚交换机、接入交换机、无线控制器、防火墙）

## 开发指南

### 添加新的 MCP 工具

1. 在 `backend/mcp/` 下创建新的 MCP 文件
2. 继承 `BaseMCP` 类
3. 实现 `execute` 方法
4. 在 `backend/agent/executor.py` 中注册新的 MCP

### 添加新的 API 端点

1. 在 `backend/api/` 下创建或修改 API 文件
2. 使用 FastAPI 装饰器定义路由
3. 在 `backend/api/__init__.py` 中导出路由
4. 在 `backend/main.py` 中注册路由

### 添加新的前端页面

1. 在 `frontend/src/pages/` 下创建 Vue 组件
2. 在 `frontend/src/router/index.ts` 中添加路由
3. 在 `frontend/src/components/TopNav.vue` 中添加导航项

## 故障排查

### 后端无法启动

1. 检查 Python 版本：`python3 --version`
2. 检查依赖安装：`pip list`
3. 检查环境变量：`cat backend/.env`
4. 查看日志：`tail -f backend/logs/app.log`

### NetBox 连接失败

1. 检查 NetBox 地址和 API Token
2. 测试 NetBox 连接：`curl -H "Authorization: Token YOUR_TOKEN" NETBOX_URL/api/dcim/devices/`

### Zabbix 连接失败

1. 检查 Zabbix 地址和 API URL
2. 检查用户名和密码
3. 查看 Zabbix API 日志

### LLM 调用失败

1. 检查 LLM API 地址是否可访问
2. 查看后端日志中的错误信息
3. 确认模型名称配置正确

### 5173 打开后是 Streamlit 页面（非预期）

现象：页面出现“对话式运维 / 模型未加载 / 使用说明”等 Streamlit 风格内容。  
原因：5173 端口被旧的 Streamlit 进程占用。

处理步骤：
1. 查占用进程：`lsof -nP -iTCP:5173 -sTCP:LISTEN`
2. 停止进程：`kill <PID>`
3. 在 `frontend/` 重新启动：`npm run dev`
4. 刷新 `http://localhost:5173`，应进入 Vue 页面（自动跳转 `/dashboard`）

## 性能优化建议

1. 使用生产级 ASGI 服务器（如 Gunicorn + Uvicorn）
2. 启用 Redis 缓存
3. 使用数据库存储会话历史
4. 配置 Nginx 反向代理
5. 启用前端资源压缩

## 安全建议

1. 不要在代码中硬编码敏感信息
2. 使用环境变量管理配置
3. 启用 HTTPS
4. 实施访问控制和审计日志
5. 定期更新依赖包
6. 限制 API 访问频率

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

[待定]

## 联系方式

[待定]

## 更新日志

### v0.1.0 (2026-01-12)

- Phase 1 基础功能完成
- AI 对话调度系统
- NetBox、Zabbix、ELK 集成
- 资产管理、告警中心、日志分析
- 移除自动化任务模块（待重构）
