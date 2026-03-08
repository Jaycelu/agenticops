# NetOps AgenticOps 重构实施路线图

日期：2026-03-08

## 1. 目标

在不打断当前主流程的前提下，将项目从“新 AgenticOps 主干 + 旧自动化兼容层并存”的过渡状态，收敛为边界清晰、命名统一、可持续扩展的稳定架构。

本轮重构优先级：

1. 统一边界和命名
2. 收敛事件到 Case 的入口关系
3. 清理 Case 主链路的 legacy 依赖
4. 逐步纯化 Memory 和 Fabric
5. 最后隔离并下线 compat 层

## 2. 当前审计结论

### 2.1 稳定主干

- `SourceEvent / CaseRecord / EvidenceItem / AgentRun / AgentClaim / MemoryEntry / RemediationPlan / ExecutionRun`
- `CaseOrchestrator`
- `Cases / Agents / Memories / Fabric` 主工作台

### 2.2 主要问题

- 事件域仍使用 `AlertEvent` 作为运行事实源，和 `SourceEvent` 并存
- `/api/automation` 兼容层仍对主工作台口径产生影响
- `CaseOrchestrator` 仍直接读取 legacy feedback 模型
- `Memory API` 仍承担 backfill 语义
- 模型配置存在 `settings.llm_*` 与运行时 `_models_store` 双真相
- `backend/services`、`backend/agent`、`backend/langchain_agent` 仍保留历史结构噪音

## 3. 阶段拆解

### 阶段 1：边界冻结

目标：建立统一的边界、命名和 ownership 规则，不先做大规模代码搬迁。

任务：

- 输出领域边界基线
- 梳理 API 归属为 `core / compat / settings / integration`
- 梳理模型归属为 `target / legacy / migration-only`
- 梳理目录责任矩阵
- 统一命名规则
- 冻结事件与 case 主链路时序
- 冻结 memory / fabric 写入策略

验收：

- 能明确回答“谁拥有哪类数据、谁可以写、谁只读兼容”

### 阶段 2：事件域收口

目标：让 Event Center 成为独立、清晰的事件域。

任务：

- 统一事件入口 contract
- 让事件 ingest 与 case 创建解耦
- 用 `decision envelope` 表达分流结果
- 逐步将 `AlertEvent` 收敛到 `SourceEvent`

验收：

- 事件可以独立入库、展示、分流，不依赖 case 已存在

### 阶段 3：Case + Agent 主链路收口

目标：让 Case Center 成为唯一智能研判主链路。

任务：

- 清除 `CaseOrchestrator` 的 legacy task / feedback 直接依赖
- 固化 agent 输入输出 contract
- 统一模型激活配置来源

验收：

- Case pipeline 不再需要读取 legacy automation 表

### 阶段 4：Memory 域纯化

目标：Memory 只负责记忆，不承担兼容回填入口。

任务：

- 将 feedback backfill 迁移到脚本或 compat
- 约束 Memory 写入来源

验收：

- `/api/memories` 不再触碰 legacy automation 表

### 阶段 5：Fabric 域纯化

目标：执行、审批、回滚全部收敛到 Fabric。

任务：

- 升格通用执行引擎
- 统一 `RemediationPlan / ExecutionRun` 为主执行模型

验收：

- Fabric 主流程不再依赖 `AutomationTask`

### 阶段 6：compat 隔离与最终下线

目标：兼容层不再污染主链路，最后可独立下线。

任务：

- `/api/automation` 迁入 compat 视角
- legacy mapping 集中到 compat bridge
- 清理旧 chat agent / 旧自动化任务叙事 / 旧前端入口

验收：

- 主系统只剩一套事件模型、一套 case 主链路、一套 fabric 执行模型

## 4. 新边界原则

### Event Center

- 拥有：外部事件接入、归一化、聚类、分流建议
- 不拥有：智能体执行、记忆沉淀、执行计划

### Case Center

- 拥有：case 生命周期、证据装配、agent pipeline、根因与处置建议
- 不拥有：原始事件接入

### Memory

- 拥有：episode / pattern / outcome / feedback 记忆
- 不拥有：迁移入口、legacy feedback 查询 API

### Fabric

- 拥有：计划、审批、执行、回滚、验证
- 不拥有：事件分流、历史兼容任务口径

### Compat

- 拥有：旧 API、旧模型映射、迁移脚本、只读兼容
- 不拥有：主流程写入权限

## 5. 本轮执行项

本轮先落地以下高优先级改造：

1. 文档化重构路线图与阶段 1 基线
2. 收口模型配置入口，修正 `api.models` 命名歧义
3. 将事件 ingest 改为“按 disposition 决定是否创建 case”
4. 将 `CaseOrchestrator` 的 legacy feedback 读取隔离到 compat 层

## 6. 风险控制

- 不在一轮内直接删除 legacy 表或 legacy API
- 新增的命名调整优先保留 shim，避免打断现有联调
- 事件入口行为变化以“更符合现有 disposition 规则”为准，不同时重写 UI 逻辑
