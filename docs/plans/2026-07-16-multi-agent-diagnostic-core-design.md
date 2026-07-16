# AgenticOps 多 Agent 诊断内核设计

## 目标与边界

本轮把现有顺序 Playbook 演进为持久化、可恢复的多 Agent 诊断图，覆盖动态任务拆解、证据闭环、多假设与诊断 Critic、预算、Checkpoint、Timeline 和异步 Worker 调度。现有认证、RBAC、PolicyGuard、审批冻结、幂等执行、Webhook Outbox、ELK 降噪、变更后验证和 Observe-only 全部保留。

本轮在 Safety Review 后停止。Agent 只能自主调用 `agent_selectable=true` 且 `read_only=true` 的工具；不得自主调用 `api.request`、`script.run` 或 `ssh.config_change`，不得执行真实设备变更。

## 现状审计结论

真实调用链为：

`Case API -> CaseOrchestrator -> PipelineRegistry -> PipelineEngine -> ContextCollector -> Triage -> Historical -> Insight(最多两轮) -> Remediation -> SafetyCritic -> StateFinalizer`

现有 Pipeline 是 JSON 配置的顺序 step/hook/有限 loop，不是持久化任务图。`AgentRunner` 每次生成一个 `AgentRun` 和一个 `AgentClaim`；`next_evidence_requests` 只存入 Claim metadata。Worker 只消费 Webhook、ELK ingestion 和 verification，没有 Case Graph 队列或恢复逻辑。

现有安全能力是真实实现：Probe Gateway 具备白名单模板、参数校验、目标解析、并发锁、脱敏和审计；PolicyGuard、计划冻结审批、执行幂等、Webhook Outbox、验证循环和 Observe-only 均有调用路径。Case 状态目前被 StateFinalizer、ExecutionService 和 VerificationService 直接赋值，必须迁移到统一状态服务。

前端为 Vue 3。Case 页面只读取 Evidence、AgentRun/Claim 和 RemediationPlan；Agent 页面展示目录与运行健康；Fabric 页面承载审批和执行。新增视图应放入 Case 详情，不新增一级菜单。

## 方案选择

采用独立的轻量持久化 Graph Engine，复用现有服务边界。

不直接扩展旧 PipelineEngine：它没有持久化任务、等待状态、租约、人工节点和恢复语义，强行扩展会继续产生状态旁路。旧 Pipeline 保留为兼容代码，但新的 `run-agents` 入口只创建 Graph Run。

不引入 CrewAI、AutoGen、LangGraph 或新消息队列。PostgreSQL 作为任务队列和状态存储，Worker 使用 `FOR UPDATE SKIP LOCKED`、租约和幂等键领取 Graph Run/AgentTask。

## 数据模型

新增：

- `agent_graph_run`：一次 Case Graph 运行，保存 graph version、状态、当前节点、租约、运行/停止原因、force restart 关系和时间戳。
- `agent_task`：持久化节点任务，支持父任务、优先级、等待状态、重试、deadline、幂等键和输入输出。
- `agent_message`：Agent、Supervisor、Probe、Policy、Human 之间的结构化消息。
- `agent_tool_call`：每次受控工具调用及 Policy 决策、结果和耗时。
- `agent_budget`：上限和消耗快照；更新使用行锁和原子校验。
- `agent_checkpoint`：Graph 状态、pending tasks、budget snapshot 和单次使用的 resume token。
- `case_timeline_event`：状态、任务、消息、工具、证据、假设、Critic、人工节点的统一投影。
- `case_state_transition`：Case 状态变更事实，含 from/to、触发者、原因、关联对象和幂等键。
- `case_hypothesis`：一等假设记录，保留 supporting/contradicting Evidence ID、缺失证据、下一步 Probe、状态与 round。

不删除旧表。`AgentRun` 增加可空 `task_id` 和 Graph Run 关联，旧数据继续可读。`EvidenceItem` 增加可空 task/tool-call/probe-run 来源关联和有效期元数据。

Case 状态枚举扩展为新状态集合，同时保留旧 `open/investigating/planned/closed` 值用于旧数据读取；新 Graph 不再写旧状态。API 对旧状态继续可查询。

## 集中式状态服务

所有新旧 Case 状态写入迁移到 `CaseStateService.transition()`。服务负责：

- 合法转换表；
- Case 行锁；
- `expected_from` 乐观校验；
- 幂等键去重；
- transition record 与 Timeline Event 同事务写入；
- actor、reason、AgentRun、Task、Evidence 和 correlation ID 关联；
- closed/last_activity/current_phase 的确定性更新。

StateFinalizer、ExecutionService、VerificationService 不再直接设置 Case 状态。

## Graph Engine 与 Worker

首个图版本：

`Normalize -> Triage -> Supervisor -> Evidence Collection -> Diagnostic Agents -> Diagnostic Critic -> Supervisor Arbitration -> Plan Candidate -> Safety Review -> Human Gate / Observe-only Stop`

Graph 定义为代码内版本化 Node/Edge 注册表，条件函数是确定性代码。Graph Engine 只调度节点，不直接 SSH 或修改设备。

每个节点落为 AgentTask。任务幂等键由 `graph_run_id + node + logical_round + target` 生成。有限并行只用于彼此独立的诊断任务；同一设备 Probe 仍受 Probe Gateway 锁约束。

Worker 每轮：

1. 领取到期且未租赁的 Graph Run；
2. 校验预算和 deadline；
3. 恢复最新 Checkpoint；
4. 领取 ready task；
5. 执行一个有界节点并提交事务；
6. 生成 Timeline、Checkpoint 和下一批任务；
7. 释放或续租。

进程在节点中断时，租约过期后由其他 Worker 重新领取。外部副作用前先写 ToolCall/ProbeRun，依赖幂等键避免重复执行。

## Supervisor

Supervisor 是结构化决策服务，不直接调用工具。输入为 Case、Evidence、Claims、Hypotheses、Memory、任务状态和预算；输出使用 Pydantic 契约：decision、next_tasks、state_transition、reason、stop_reason。

优先使用确定性规则判断阶段、预算、证据新鲜度、确认阈值和停止条件。LLM 只在复杂仲裁时提供候选建议，最终转换仍由确定性校验器执行。

## Evidence 闭环与 Tool Loop

Diagnostic Agent 只能返回白名单 `EvidenceRequest`。Supervisor 校验 probe ID、NetBox target、参数和目标范围后创建 Evidence Task 与 `evidence_request` Message。

Evidence Task 通过 Tool Registry 和 PolicyGuard 调用 Probe Gateway。所有成功结果写入 EvidenceItem，并生成 `evidence_response` Message；失败也持久化 ToolCall、Task error 和 Timeline，不吞异常。随后创建下一轮 Diagnostic Task，递增 `insight_round`。

AgentRunner 支持有界 Decision/Tool/Observation 循环：单 Agent 默认 3 次工具调用，单 Case 默认 10 次 Probe。每次调用先消耗预算，再校验 `agent_selectable`、`read_only`、target scope、vendor、参数 schema 和 PolicyGuard。

## 多假设与 Critic

Insight Agent 输出经契约校验后写入 `case_hypothesis`。假设状态为 proposed、supported、weakened、rejected、confirmed。

Diagnostic Critic 与现有 Safety Critic 分离。Diagnostic Critic 检查反证、时效、来源独立性、因果关系和更简单解释，输出 accept/revise/reject 并引用 Evidence ID。

Supervisor 只有在配置化阈值全部满足时确认根因：置信度、两个独立来源或直接设备证据、无未处理高权重反证、Critic 未拒绝、Evidence 未过期。阈值集中在 settings/config，不散落在 Agent。

## API 与兼容

`POST /api/cases/{case_id}/run-agents` 默认返回 `202 Accepted`，创建或复用运行中的 Graph Run。保留 `case_id` 等主要字段，并新增 status、execution_mode、graph_run_id、current_state、current_node、queued、already_running、message、legacy_result。

`force_restart=true` 需要新增的 Graph 管理权限；它取消旧运行、保留全部记录、审计后创建新 Graph Run。`wait=true` 仅轮询持久化状态，严格限制 timeout，超时不取消任务。

新增只读接口：Graph Run 列表/详情、Timeline、Hypotheses、Budget。旧 Evidence、Agent 和 Plan 接口保持。

仓库中其他直接调用 `run_case_pipeline()` 的 ingestion/log/event 路径统一改成 enqueue Graph Run，避免后台入口继续同步执行旧 Pipeline。

## 前端

Case 页面增加运行按钮和持久化运行状态。收到 graph_run_id 后轮询 Graph Run 与 Timeline；页面刷新时从运行列表恢复。

详情页增加：

- Agent Timeline：状态、Supervisor、Task、Message、ToolCall、Evidence、Hypothesis、Critic、Human；
- Hypothesis Board：候选、置信度、支持、反证、缺失和状态；
- Budget Panel：runs、LLM、tool、probe、replan、runtime、target devices 和 exhausted 原因。

完成后刷新旧 Case、Agent、Evidence 和 Plan 数据。当前不引入 WebSocket/SSE。

## 可观测性与安全

新增需求中的 Prometheus 指标。日志上下文统一包含 request_id、case_id、task_id、agent_run_id、tool_call_id、graph_node、correlation_id。

Agent 可选工具默认拒绝；旧 catalog 缺少新字段时按 `agent_selectable=false`、`read_only` 从 capability 推导但不授予 Agent 权限。高风险通用工具仅保留人工/既有执行路径。

首次部署和 Compose 继续默认 `AUTOMATION_OBSERVE_ONLY=True`。Safety Review 之后只进入人工等待或 Observe-only Stop。

## 测试策略

先固定兼容的 `openai/httpx` 版本并增加无网络 LLM Client 初始化测试，恢复现有单测基线。

单元测试覆盖状态机、Task 生命周期、预算原子消耗、EvidenceRequest、假设仲裁、Diagnostic Critic、Tool Policy、Checkpoint/Resume 和幂等。

集成测试使用 PostgreSQL 和可控 Fake Adapter，覆盖完整证据闭环、第二轮诊断、Critic 分支、Planning/Escalated、租约恢复、预算耗尽和 Observe-only。

场景测试覆盖 BGP、接口 Down、Zabbix 误报、ELK 风暴、NetBox 缺设备、凭据不可用、证据冲突和无法确认。

最后运行单测、PostgreSQL migration/integration、前端构建、Compose config、容器健康检查和 CI 等价命令。

## 迁移与回滚

Alembic 从 `0010_worker_runtime` 线性升级。升级先增加表、列、索引和枚举值，再部署兼容代码。旧 Case 不回填 Graph 数据。

数据库 downgrade 只删除本轮新增对象并移除可空关联列；PostgreSQL enum 值不做破坏性删除。应用回滚到旧版本前必须停止新 Worker，避免旧应用无法理解新状态。
