# NetOps Platform

面向网络运维的自动化平台（资产 + 告警 + 日志 + 自动化闭环）。

当前正式形态是：
- 前端：Vue 3 + Vite
- 后端：FastAPI + SQLAlchemy
- 数据库：PostgreSQL（推荐独立自动化数据库）

## 当前功能范围

### 前端主模块（导航可见）
- 资产：设备/IP/站点等资产视图
- 告警：监控告警查询与分析
- 日志：日志查询与分析
- 自动化中心：采样、研判、任务、审计、反馈
- 异常类型管理
- 设置：模型配置、SSH 凭据与设备绑定

### 后端核心能力
- 自动化日志采样（ELK）
- 异常判定与分层触发（实时严重事件 + 周期累计事件）
- 拓扑感知研判（NetBox 上下文）
- SSH 实测闭环（凭据管理、连通性检查、命令采集）
- 自动化任务审计追踪（Trigger / Inspection / Reasoning / Conclusion）
- 反馈闭环与统计学习
- 数据保留与定时清理

说明：仓库中仍保留部分历史 API（如 chat/sessions），但不属于当前前端主流程。

## 架构

```text
┌──────────────────────────────────────────────────────────────┐
│                       Vue Frontend                           │
│  Assets / Alerts / Logs / Automation / AbnormalTypes / Settings
└───────────────────────────────┬──────────────────────────────┘
                                │ REST API
┌───────────────────────────────▼──────────────────────────────┐
│                        FastAPI Backend                        │
│  api/assets  api/alerts  api/logs  api/automation  api/ssh   │
│  services/log_sampler  services/automation_orchestrator       │
│  services/context_aware_diagnosis  services/ssh_service       │
└───────────────┬───────────────────────┬───────────────────────┘
                │                       │
        ┌───────▼────────┐      ┌──────▼─────────┐
        │ PostgreSQL      │      │ External Systems│
        │ netops_automation│     │ NetBox/Zabbix/ELK/LLM
        └─────────────────┘      └─────────────────┘
```

## 自动化闭环流程

1. ELK 日志采样（定时）
2. 异常判定（严重实时 + 普通周期阈值）
3. NetBox 拓扑上下文补全
4. SSH 现场检查（按厂商命令模板）
5. AI 最终结论与建议
6. 生成自动化任务与审计轨迹
7. 人工反馈回流统计与校准

## 目录结构（精简）

```text
backend/
  api/
    assets.py alerts.py logs.py automation.py ssh_management.py
  config/
    settings.py site_config.py
  mcp/
    netbox_mcp.py zabbix_mcp.py elk_mcp.py
  models/
    automation.py llm_client.py
  services/
    log_sampler.py
    automation_orchestrator.py
    context_aware_diagnosis.py
    ssh_service.py
    data_retention_service.py
  scripts/
    init_automation_db.py
    cleanup_automation_data.py
  main.py
frontend/
  src/
    pages/
    components/
    api/
docs/
  AUTOMATION_DATABASE_DESIGN.md
```

## 环境要求

- Python 3.10+
- Node.js 16+
- PostgreSQL 14+

## 数据库建议（PostgreSQL）

推荐同一实例下分库：
- `netops`（主业务）
- `netops_automation`（自动化中心高频数据）

后端连接策略：
- 优先 `AUTOMATION_DATABASE_URL`
- 未配置时回退 `DATABASE_URL`

详细表设计见：`docs/AUTOMATION_DATABASE_DESIGN.md`

## 快速开始

### 1) 配置环境变量

```bash
cp deploy/env.example backend/.env
```

重点变量：
- `DATABASE_URL`
- `AUTOMATION_DATABASE_URL`
- `NETBOX_*` / `ZABBIX_*` / `ELK_*`
- `LLM_API_URL` / `LLM_MODEL_NAME`
- `RETENTION_*_DAYS`

### 2) 初始化 PostgreSQL（示例）

```sql
CREATE USER netops WITH PASSWORD 'netops';
CREATE DATABASE netops OWNER netops;
CREATE DATABASE netops_automation OWNER netops;
```

### 3) 初始化自动化数据库

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 scripts/init_automation_db.py
```

### 4) 启动后端

```bash
cd backend
source venv/bin/activate
python3 main.py
```

### 5) 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问：
- 前端：`http://localhost:5173`
- 后端健康检查：`http://localhost:8000/health`
- API 文档：`http://localhost:8000/docs`

## 数据清理与保留

- 后端内置任务：每 12 小时执行一次自动化数据清理
- 手动执行：

```bash
cd backend
source venv/bin/activate
python3 scripts/cleanup_automation_data.py
```

默认保留周期（天）：
- `log_sample`: 30
- `raw_anomaly`: 30
- `log_analysis_result`: 60
- `automation_task`: 90
- `automation_action_log`: 90
- `automation_approval`: 180
- `automation_task_feedback`: 180
- `abnormal_tracker_state`: 7

## 主要 API（当前主流程）

- `/api/assets/*` 资产查询
- `/api/alerts/*` 告警查询
- `/api/logs/*` 日志查询/分析
- `/api/automation/*` 自动化中心（样本、研判、任务、反馈、统计）
- `/api/ssh/*` SSH 凭据、设备绑定、连通性检查、命令执行

## 备注

- 历史 Streamlit 原型目录：`frontend/streamlit/`，不属于当前正式启动流程。
- 如需补充 ER 图或分区表方案，可在 `docs/` 下继续扩展。
