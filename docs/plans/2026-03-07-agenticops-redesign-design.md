# NetOps AgenticOps 重构设计

日期：2026-03-07

## 1. 目标

将当前以 `异常类型 + 单编排器` 为核心的自动化链路，重构为以 `Case + 多 Agent + 记忆系统 + Automation Fabric` 为核心的 AgenticOps 架构。

首期范围：

- 数据源：ELK、Zabbix、NetBox、SSH
- 智能体：Alert Triage、Historical Analysis、Insight Analysis、Autonomous Remediation
- 执行：沿用现有 SSH / script / API executor
- UI：后续切为左侧导航 + 右侧工作区

非首期范围：

- Ansible 真正接入
- New Relic 等第三方 APM 真正接入
- 旧模块完全删除

## 2. 总体分层

### 2.1 数据源层

- ELK Adapter：日志检索、时间窗口采样、日志签名聚合
- Zabbix Adapter：告警、触发器、主机状态、关键指标
- NetBox Adapter：设备、站点、角色、拓扑、链路
- SSH Evidence Adapter：现场证据采集

输出统一标准化证据对象，禁止上层 Agent 直接拼接原始数据。

### 2.2 分析引擎层

- Case Orchestrator：仅负责 case 生命周期与调度
- Alert Triage Agent：分类、去重、富化、初判
- Historical Analysis Agent：历史相似案例与成功动作检索
- Insight Analysis Agent：日志、拓扑、SSH 交叉验证
- Autonomous Remediation Agent：生成修复计划并触发执行安全门控

### 2.3 记忆系统层

- Episode Memory：Case 全过程
- Pattern Memory：日志签名、告警组合、拓扑模式
- Outcome Memory：动作与结果
- Feedback Memory：人工反馈与复盘

### 2.4 输出层

- Case API
- Agent API
- Memory API
- Fabric API
- 驾驶舱 / Case 中心 / 智能体中心 / 记忆中心 / 自动化执行中心

## 3. 硬约束

- Agent 只能基于标准化证据对象推理，不能直接虚构事实。
- 所有 Agent 输出必须包含：`claim`、`evidence_refs`、`confidence`、`gaps`。
- 未经证据验证的判断必须显式标记为 `hypothesis`。
- 自动执行必须经过 Remediation Agent 和 Safety Gate，诊断 Agent 无权直接执行。

## 4. 数据模型

新增核心模型：

- `source_event`
- `case_record`
- `evidence_item`
- `agent_run`
- `agent_claim`
- `memory_entry`
- `remediation_plan`
- `execution_run`

旧模型处理策略：

- `AlertEvent`：保留，逐步迁移到 `source_event`
- `LogSample`：保留，转为采样事实
- `LogAnalysisResult`：逐步由 `agent_run + agent_claim` 替代
- `AutomationTask`：逐步由 `remediation_plan + execution_run` 替代
- `AutomationTaskFeedback`：并入记忆系统
- `AbnormalType*`：第四阶段删除

## 5. API 边界

### 5.1 Case API

- `GET /api/cases/overview`
- `GET /api/cases`
- `POST /api/cases`
- `GET /api/cases/{case_id}`
- `GET /api/cases/{case_id}/evidence`
- `GET /api/cases/{case_id}/agents`
- `GET /api/cases/{case_id}/plans`

### 5.2 Agent API

- `GET /api/agents/catalog`
- `GET /api/agents/health`
- `GET /api/agents/runs`
- `GET /api/agents/runs/{run_id}`

### 5.3 Memory API

- `GET /api/memories/overview`
- `GET /api/memories`
- `GET /api/memories/{memory_id}`

### 5.4 Fabric API

- `GET /api/fabric/overview`
- `GET /api/fabric/plans`
- `GET /api/fabric/plans/{plan_id}`
- `GET /api/fabric/executions`
- `GET /api/fabric/executions/{execution_id}`

## 6. 分阶段任务清单

### 阶段 1：新数据模型和 API 边界

- 新增 AgenticOps 数据模型
- 新增 Pydantic schema
- 新增 `cases / agents / memories / fabric` 路由
- 挂载到 FastAPI
- 保持与旧自动化链路并存

验收标准：

- 服务可启动
- 新表可创建
- 新 API 可返回空结果或基础聚合结果

### 阶段 2：多 Agent 主链路

- 新增 `backend/agents/` 与 `backend/engines/`
- 实现 Case Orchestrator
- 实现四类 Agent 的输入输出 contract
- 将 ELK/Zabbix/手动触发统一接入 case intake
- 将旧自动化链路改为兼容入口

验收标准：

- 可从源事件创建 case
- 至少能完整跑通 triage -> historical -> insight -> remediation draft

### 阶段 3：驾驶舱与 Case 中心

- 重构驾驶舱指标口径为 case / agent / memory / fabric
- 新增 Case 中心主页面
- 将旧事件/自动化任务的工作流逐步并到 Case 中心

验收标准：

- 驾驶舱不再依赖异常类型指标
- Case 中心可以查看 case 详情、证据、agent 输出、执行计划

### 阶段 4：导航重构与旧页面清理

- 顶部导航改左侧导航
- 新建智能体中心、记忆中心、自动化执行中心
- 清理异常类型页面
- 下线旧 `backend/agent/*` 和旧异常类型模块

验收标准：

- 左侧导航与新模块一致
- 旧异常类型页面和入口消失
- 新架构页面可替代旧自动化中心主流程

## 7. 风险与控制

- 风险：新旧任务模型并存期间数据口径混乱
  - 控制：驾驶舱切换前不替换旧统计接口
- 风险：Agent 输出不可审计
  - 控制：强制 `agent_run + agent_claim + evidence_refs`
- 风险：直接删除旧异常类型导致主流程断裂
  - 控制：先并存新 case 链路，第四阶段再删除旧模块

## 8. 本次执行范围

本次开始执行阶段 1：

- 完成新数据模型
- 完成新 API skeleton
- 完成 FastAPI 挂载
- 完成基础校验

## 9. 执行状态跟踪

### 新增优化方向（2026-03-08）

在本次基础重构之上，新增一条“Source-Centric AgenticOps”优化线，详细设计见：

- [2026-03-08-source-centric-agenticops-design.md](./2026-03-08-source-centric-agenticops-design.md)

新增原则：

- NetBox 是唯一真实资产与拓扑源
- ELK 是唯一日志源
- Zabbix 是唯一告警与实时状态源
- SSH 从默认诊断链路降级为执行通道
- 事件中心升级为统一事件工作台
- 后续新增 `Zabbix 中心` 作为一等前端数据源模块

### 已完成

- 阶段 1：新增 AgenticOps 数据模型、Schema、Cases/Agents/Memories/Fabric API，并完成 FastAPI 挂载
- 阶段 2：新增 ELK/Zabbix/NetBox/SSH adapters，完成 Case Orchestrator 与四类运维 Agent 的最小闭环
- 阶段 2：事件与日志入口已支持接入 case intake，并可沉淀 episode / pattern / outcome 记忆
- 阶段 3：驾驶舱已切换为 case / agent / memory / fabric 口径
- 阶段 3：Case 中心、智能体中心、记忆中心、执行中心页面已落地
- 阶段 4：顶部导航已替换为左侧导航，右侧工作区已按新模块重排
- 阶段 4：旧 chat-agent、旧 sessions API、旧 abnormal-types API 已下线运行入口
- 阶段 4：旧 `frontend/src/pages/automation/*` 页面已删除，旧自动化路由统一重定向到新工作台
- 阶段 4：`log_sampler` 与手动触发接口已切换为 `signal/pattern/case pipeline` 语义，不再依赖异常类型模块做主流程判定
- 阶段 4：旧 `automation_orchestrator` 已降级为兼容代理，`abnormal_type_service / abnormal_tracker` 已从运行层移除
- 阶段 4：`models/automation.py` 中的 `AbnormalType*` 已移除
- 阶段 4：`LogSample.abnormal_type` 已从 ORM 模型移除，兼容展示改为读取 `raw_data.signal_summary.primary_signal`
- 阶段 4：`AbnormalTrackerState` 已从 ORM 与 retention 清理逻辑中移除
- 阶段 4：`state_aggregator / abnormal_upgrader / diagnosis_service / context_aware_diagnosis` 已切换为 `signal_key / needs_escalation` 主语义，旧 `abnormal_type / needs_upgrade` 仅作兼容镜像
- 阶段 4：旧自动化任务查询 API 已兼容映射到 `RemediationPlan / ExecutionRun`，旧 `/api/automation/tasks*` 可读取新 Fabric 数据
- 阶段 4：事件中心、日志中心已支持直接打开关联 Case，旧入口的主操作流已进一步收敛到 `Case 中心`
- 阶段 4：事件中心 `dispatch-readonly` 已改为重跑 `case pipeline`，不再为新流程创建旧 `AutomationTask`
- 阶段 4：无活跃调用的 `diagnosis_service / context_aware_diagnosis` 已删除，避免旧研判链路回流
- 阶段 4：`log_sampler` 中未接入主流程的旧 `rule_evaluator / llm_diagnosis / decision_task` 兼容链路已删除
- 阶段 4：旧 `task approval / feedback` 接口已支持兼容映射到 `RemediationPlan / MemoryEntry`
- 阶段 4：已新增历史补迁脚本 `backend/scripts/backfill_agenticops_data.py`，用于将旧 `AutomationTask / AutomationTaskFeedback` 回填到 `SourceEvent / CaseRecord / RemediationPlan / MemoryEntry`
- 阶段 4：无运行层引用的 `approval_service / confirmation_service / decision_service / event_skill_service` 已删除
- 阶段 4：README 已按新 AgenticOps 架构重写，并补充 `backend/.env.example` 与 `frontend/.env.example`
- 阶段 4：NetBox / ELK / Zabbix 凭据已迁移到 `设置 -> 集成配置`，敏感字段改为数据库密文存储，使用 `APP_SECRET_KEY` 解密
- 阶段 4：ELK 日志范围已从硬编码 `base_configs` 迁移到 `log_scope` 数据模型与设置中心，可绑定 NetBox Site、别名和自定义时间窗
- 阶段 4：日志页已切换为“日志范围”视图，后端新增 `/api/settings/log-scopes` 与 `/api/logs/scopes`
- 阶段 4：已新增 `backend/scripts/import_log_scopes.py`，支持从 JSON 导入日志范围配置

### 进行中

- 阶段 4：旧自动化页面路由已完成重定向，旧自动化任务 API 仍以兼容视图保留，尚未完全下线
- 阶段 4：少量旧服务返回体仍带 `abnormal_type / needs_upgrade` 兼容字段，但主流程已切到 `signal` 语义
- 阶段 4：`Execution/Fabric` 链路已覆盖新工作台主流程，但 `/api/automation` 兼容层仍保留部分 legacy 数据模型输出
- 阶段 4：历史补迁脚本已完成，但当前环境未启动 PostgreSQL，尚未完成一次真实 dry-run/正式 backfill 验证
- Source-Centric 优化：阶段 1 文档与任务清单已启动，阶段 3 的“默认诊断链路去 SSH 化”准备开始

### 未开始

- 执行一次真实的 PostgreSQL backfill dry-run / 正式补迁并核对结果
- Source-Centric 优化：统一事件模型、Zabbix 中心、事件中心重构、驾驶舱降噪/MTTR 指标重做
