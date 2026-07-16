# AgenticOps v0.2.0

发布日期：2026-07-16

v0.2.0 将 Case 诊断从同步、固定顺序的 Agent 调用升级为持久化、可恢复的异步多 Agent Graph。本版本仍以诊断闭环为边界，不开放高风险自动执行。

## 主要变化

- 新增持久化 `AgentGraphRun`、`AgentTask`、`AgentMessage`、`AgentToolCall`、`AgentBudget`、`AgentCheckpoint`、`CaseTimelineEvent`、`CaseStateTransition` 和 `CaseHypothesis`。
- 新增 Case Supervisor，根据 Case、Evidence、Claims、Memory、Critic 结果和预算动态生成下一步任务。
- Evidence Request 使用白名单 Schema；只读 Probe 结果自动写入 Evidence，并重新触发诊断轮次。
- 新增独立 Diagnostic Critic，检查反证、证据时效、来源独立性、因果关系和更简单解释。
- 新增集中式 Case 状态转换服务，合法性校验、审计、关联对象和 Timeline 写入保持幂等。
- Worker 通过数据库租约与 Checkpoint 推进 Graph，进程重启后能够恢复未完成运行。
- Case 详情页新增 Agent Timeline、Hypothesis Board、Budget Panel 和 Graph Run 轮询展示。
- Tool Catalog 新增 Agent 可选、只读、目标范围、厂商、输出解析器和 Evidence Mapper 约束，兼容旧目录。
- 增加 Agent Task、消息、工具、预算、状态转换、恢复、假设和人工升级指标及关联日志字段。
- 固定兼容的 OpenAI/httpx 依赖组合，并增加无 API Key 下的最小 LLM Client 初始化测试。

## API 语义变化

`POST /api/cases/{case_id}/run-agents` 路径保留，但默认语义调整为“Graph Job 已受理”：

- 默认返回 `202 Accepted` 和 `graph_run_id`，不再伪装为整轮诊断已经完成。
- 同一 Case 已有活动 Graph 时幂等返回该运行，不重复创建任务。
- `force_restart=true` 需要 `agent_graphs.restart` 权限；旧运行被取消，但旧 Checkpoint、Evidence、Claim 和 Timeline 不删除。
- `wait=true&timeout_seconds=30` 是有严格上限的兼容模式；等待超时后 Graph 仍由 Worker 继续执行。

新增查询接口：

- `GET /api/cases/{case_id}/graph-runs`
- `GET /api/cases/{case_id}/graph-runs/{graph_run_id}`
- `GET /api/cases/{case_id}/timeline`
- `GET /api/cases/{case_id}/hypotheses`
- `GET /api/cases/{case_id}/agent-budget`

## 数据库升级

本版本数据库 head 为 `0011_multi_agent_graph`。升级前必须停止 API/Worker 写入并执行 `pg_dump -Fc`；随后运行：

```bash
docker compose run --rm migrate
```

完整步骤和回滚边界见 [部署手册](../DEPLOYMENT.md) 与 [0011 迁移/回滚说明](./MIGRATION_0011_MULTI_AGENT_GRAPH.md)。旧 Case、Evidence、Claim、审批和执行记录不会被删除。

## 安全边界

- 首次部署和升级后仍默认 `AUTOMATION_OBSERVE_ONLY=True`。
- Agent 只能自主选择同时满足 `agent_selectable=true`、`read_only=true` 的工具。
- 所有 Agent 工具调用都经过 Tool Registry、PolicyGuard 和 Probe Gateway，并生成 Tool Call 审计与 Evidence。
- `api.request`、`script.run`、`ssh.config_change` 仅保留兼容，不向 Agent 自主扩权。
- Graph 在 Safety Review 后进入 Human Gate 或 Observe-only Stop；本版本不会执行真实设备变更。

## 已知限制

- 尚未开放高风险自动执行，也没有绕过既有审批、冻结计划和幂等执行链路。
- 前端实时状态使用轮询，尚未提供 SSE/WebSocket。
- Human Gate 的专用交互式恢复接口仍待下一阶段完善。
- 自动化测试中的 NetBox、ELK、Zabbix、设备和 LLM 均使用可控 Fake Adapter；真实生产集成仍需按发布门禁完成联调。
- 多实例 Worker 通过数据库租约协调，但生产容量和故障切换仍需在目标环境验证。

## 验证范围

发布门禁覆盖后端单元/集成/场景测试、真实 PostgreSQL 迁移、Alembic downgrade/upgrade、前端生产构建、Compose 全栈健康检查、Ruff、Bandit、pip-audit 和 Python compileall。具体结果以 GitHub Release 对应提交的 CI 记录为准。
