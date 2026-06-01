# AgenticOps v2 — 方案评审与改造路线图

**版本**: v1.0
**日期**: 2026-05-15
**范围**: 评审外部（GPT）架构建议，基于实际代码梳理系统现状，给出分阶段改造任务计划。Phase 1（Tool Registry + Policy Guard + 执行闭环）给出可直接落地的详细设计。
**结论性质**: 本文档所有"现状"判断均来自对 `backend/` 源码的逐文件阅读，非基于 PRD 或前端页面名推断。

---

## 一、执行摘要

外部那份 GPT 分析，**架构愿景方向是对的，但对项目现状的判断严重失真**。它几乎可以确定只看了 `PRD.md` 和前端路由页面名，没有读后端代码。它的核心论断"项目最大的问题是缺少 Agent Runtime""Agents 只是展示智能体""Events 只是事件中心"——与代码事实不符。

实际情况：后端**已经是一个事件驱动、证据驱动、多 Agent 编排的系统**，完成度约 65–70%。`engines/case_orchestrator.py` 就是 GPT 说"缺失"的 Agent Runtime；`harness/contracts.py` 就是它说"最关键但没有"的 Evidence Bundle；`models/agenticops.py` 已经把 SourceEvent / Case 状态机 / EvidenceItem / AgentRun / AgentClaim / MemoryEntry / RemediationPlan / ExecutionRun 全部建好了。

**风险**：若把 GPT 那段"给 Codex 的第一轮重构任务"原样执行，Codex 会新建一套 `backend/app/agent_runtime/`、`backend/app/evidence/`、`backend/app/pipelines/` …… 与现有的 `engines/`、`harness/`、`agents/`、`adapters/`、`models/agenticops.py` 完全平行。结果是把一套能跑的架构分叉成两套，得不偿失。

**正确做法**：不另起炉灶，在现有 `engines/ harness/ agents/ adapters/` 之上做**增量加固**，集中火力补真实的 gap。本文档第四节给出 5 阶段路线图，第五节给出 Phase 1 详细设计。

---

## 二、GPT 方案评审

### 2.1 GPT 判断错的部分：它说"要新增"，其实代码里早已存在

| GPT 的论断 / 建议新增 | 代码中的实际状态 | 证据位置 |
|---|---|---|
| "缺少 Agent Runtime"（称为最大问题） | 已有完整编排器：多 Agent 串行 + gap 驱动补采 + 置信度驱动多轮 | `engines/case_orchestrator.py` |
| Event Ingestion / Event Normalizer | 已有：定时采样 → 标准化事件 → 自动研判 disposition | `services/log_sampler.py`、`models/agenticops.py:SourceEvent`、`services/event_decision_service.py` |
| Case State Machine | 已有：9 态枚举 open→triaged→investigating→planned→executing→verifying→resolved→closed→escalated | `models/agenticops.py:CaseStatus` |
| Evidence Bundle（"最关键的数据模型，缺失"） | 已有，且是带版本、可回放的 | `harness/contracts.py:EvidenceBundle`、`models/agenticops.py:EvidenceItem` |
| 工作流型 Agent + 结构化 JSON 输出 | 已有 4 个 Agent，输出 `AgentClaim`（claim_type / confidence / evidence_refs / gaps / next_evidence_requests） | `agents/`、`models/agenticops.py:AgentClaim` |
| Memory 分层 | 已有 4 类：episode / pattern / outcome / feedback | `models/agenticops.py:MemoryType`、`services/memory_ingestion_service.py` |
| 三层降噪 | 已有规则 disposition + cluster 窗口升级 + 跨源关联（拓扑层弱，见 gap） | `services/event_decision_service.py:_evaluate / enrich_decision_for_context` |
| Verifier / 验证恢复 | 已有只读复查（Zabbix/ELK 快照） | `services/post_execution_verification_service.py` |
| "借鉴 Harness" | 代码里已在用 harness 命名与契约（replay harness、harness_trace） | `harness/contracts.py`、`engines/case_orchestrator.py` |
| Guarded Remediation + 审批流 | 已有 `RemediationPlan`（risk/approval/rollback/safety_checks）+ 审批 API + observe-only 开关 | `models/agenticops.py:RemediationPlan`、`api/fabric.py`、`services/fabric_plan_service.py` |
| RCA 输出多假设 | `AgentClaim` 已带 confidence + gaps + next_evidence_requests（部分实现，见 gap） | `agents/insight_analysis_agent.py` |

### 2.2 GPT 判断对的部分：这些是真实 gap

抛开对现状的误判，GPT 指出的方向里有几个确实是当前系统的薄弱点：

**G1 — 执行闭环是断的（最严重，已确认）**
`ExecutionRun` 在整个代码库中**只有模型定义，没有任何代码创建它**。`services/execution_engine.py` 的 `ExecutionEngine.execute_action` 定义了但**从未被调用**，三个执行器（`api_executor` / `notification_executor` / `script_executor`）从未 `register_executor`。即 `execution_engine` + 三个 executor 当前是一整块**死代码**。`post_execution_verification_service` 在消费一个永远不会产生的 `SUCCEEDED` 状态的 `ExecutionRun`。`api/fabric.py` 能列计划、能审批，但**没有"执行"端点**。→ 计划生成后链路终止于 `CaseStatus.PLANNED`，无法真正流转。

**G2 — Policy 是"触发匹配器"，不是"安全护栏"**
`services/policy_matcher.py` 只做"日志采样匹配 DIAGNOSIS 类 `AutomationPolicy`"的触发判断。在"已批准计划 → 工具执行"之间**没有一道策略门**做风险分级、命令白/黑名单、核心设备高危动作拦截。当前唯一的执行门控是 `autonomous_remediation_agent.py` 里一句硬编码：`not is_observe_only and confidence>=0.85 and priority in {P2,P3}` → `execution_mode=auto`。`execution_engine` 内虽有 observe-only 拦截逻辑，但因 `execute_action` 从未被调用而失效。

**G3 — 没有统一的 Tool Registry**
执行能力是散的：`api_executor` / `notification_executor` / `script_executor` / `ssh_service` / `ssh_adapter` 各自为政，没有中央注册表声明每个工具的 `risk_level`、允许/禁止命令模式、`requires_approval`、observe/execute 模式、超时、是否审计。无法对"工具调用"做统一治理。

**G4 — 没有 Watcher / Safety Critic**
4 个 Agent 是 triage / historical / insight / remediation，**没有独立的旁路监督者**审查 Agent 决策，没有熔断机制（同一设备短时间多次修复→停）。这是 GPT 文档里最有价值的一个想法。

**G5 — 没有 Pipeline-as-Code**
`case_orchestrator.run_case_pipeline` 把"triage→historical→insight×(1~2)→remediation"的顺序**硬编码在 Python**，没有 YAML 流程定义、没有按故障类型的 playbook、没有可配置的 stage/step/trigger。

**G6 — Memory 检索是纯关键词的**
`case_orchestrator._find_memory_hits` 明确标注 "RAG-lite, no vectors"，靠 token 子串匹配。规模上来后召回质量会下降。GPT 的 pgvector 建议合理，但优先级低。

**G7 — 拓扑降噪弱、Agent 偏规则化**
跨源关联有了（`event_decision_service`），但没有真正的拓扑衍生告警归并（上联 down → 下游 AP 告警归并）。`autonomous_remediation_agent` 基本是规则逻辑而非 LLM 多假设推理；`AgentClaim` 有 confidence/gaps 但尚未产出真正的"假设树"（待确认 insight agent 是否调用 `llm_client`）。

### 2.3 评审结论

GPT 的"目的地"基本正确，且与项目当前的演进方向一致；但它的"施工方案"（在 `backend/app/` 下重建 8 个模块）对本代码库是错的，会造成架构分叉。**采纳其方向，弃用其施工方案**。真实优先级：G1/G2/G3 > G4 > G5 > G7 > G6。

---

## 三、当前系统真实架构（基于代码梳理）

### 3.1 核心数据模型（`models/agenticops.py`）

```
SourceEvent      标准化事件（dedup_key 去重，raw/normalized payload，9 态来源状态）
CaseRecord       Case 主体（case_code、9 态状态机 CaseStatus、current_phase、risk/priority）
EvidenceItem     证据项（7 种 EvidenceType，confidence、freshness、fingerprint、payload）
AgentRun         Agent 执行记录（input/output payload、duration、status）
AgentClaim       Agent 结构化主张（claim_type、confidence、evidence_refs、gaps、4 态 ClaimStatus）
MemoryEntry      记忆条目（4 类 MemoryType：episode/pattern/outcome/feedback）
RemediationPlan  修复计划（8 态状态、execution_mode、approval_status、risk、rollback、safety_checks）
ExecutionRun     执行运行（executor_type、audit_trail、7 态状态）—— 当前无人创建（G1）
```

辅助模型在 `models/automation.py`（Site / LogSample / RawAnomaly / AutomationPolicy / SSHCredential 等）、`models/automation_settings.py`、`models/integration_settings.py`、`models/log_scope.py`。

### 3.2 主链路（事件 → Case → 计划）

```
log_sampler.sample_site_logs                      定时从 ELK 采样（按 site，APScheduler）
  └─ _aggregate_logs_by_device                    按设备聚合 + 指纹去重
  └─ _write_samples_to_db                         写 LogSample / RawAnomaly
       └─ _upsert_sample_signal_event             生成 SourceEvent + event_decision 快照
       └─ _trigger_diagnosis_for_abnormal_samples 异步触发
            └─ _create_case_for_sample_with_db
                 └─ case_orchestrator.intake_case        建 SourceEvent + CaseRecord + 首个 EvidenceItem + episode memory
                 └─ case_orchestrator.run_case_pipeline  ↓

run_case_pipeline:
  _collect_runtime_context     elk/netbox/zabbix adapter 采集 → 写 EvidenceItem
  build_evidence_bundle_dict   构建 EvidenceBundle 快照（harness/contracts）
  _find_memory_hits            关键词召回历史记忆
  ── alert_triage_agent ──────────────────────────┐
  _supplement_runtime_after_triage  按 triage 的 gaps 补采证据
  ── historical_analysis_agent ───────────────────┤  每个 Agent → AgentRun + AgentClaim
  ── insight_analysis_agent ×(1~2 轮，置信度驱动) ──┤
  ── autonomous_remediation_agent ────────────────┘
  _create_remediation_plan     生成 RemediationPlan(status=DRAFT)
  _store_*_memory              episode / pattern / outcome 记忆沉淀
  case.status = PLANNED        ←—— 链路在此终止（G1：之后无法执行）
```

### 3.3 Fabric / 执行侧（`api/fabric.py` + `services/fabric_plan_service.py`）

已实现：`GET /overview`、`GET/list plans`、`POST /plans/{id}/approval/initiate`、`/approval/decision`、`/approval/history`、`POST /plans/{id}/feedback`、`GET/list executions`、`POST /executions/{id}/verify-readonly`。
**缺失**：`POST /plans/{id}/execute`（G1）。

### 3.4 执行器现状（全部待接线）

| 文件 | 状态 |
|---|---|
| `services/execution_engine.py` | `ExecutionEngine` / `Executor` 抽象 / `ExecutorType{SCRIPT,API,NOTIFICATION}` / `RetryPolicy` / observe-only 拦截 —— 但 `execute_action` 从未被调用 |
| `services/api_executor.py` | `APIExecutor` 全局实例，未注册 |
| `services/notification_executor.py` | `NotificationExecutor`（钉钉）全局实例，未注册 |
| `services/script_executor.py` | `ScriptExecutor` 全局实例，未注册 |
| `services/ssh_service.py` / `adapters/ssh_adapter.py` | SSH 凭据管理 + `execute_commands` + `build_diagnostic_commands`（独立于 execution_engine） |

### 3.5 配置与设置

- `config/settings.py`：环境变量（含 `automation_observe_only`、`frontend_url` 等）
- `config/site_config.py`：站点级配置（采样间隔、ELK scope、采集策略、feedback 学习策略）
- `config/pipeline_thresholds.py`：cluster/cross-source 阈值常量
- `services/automation_settings_service.py`：DB 中的 `automation_mode`（`observe_only` / `auto`），运行时可切换

---

## 四、改造路线图（5 阶段）

**总原则**
1. 不新建 `backend/app/`，所有改造长在现有 `engines/ harness/ agents/ adapters/ services/ models/` 之上。
2. 每阶段交付可独立验证的能力，不破坏现有主链路。
3. 安全相关能力（Policy / Tool 治理 / 执行闭环）优先于功能扩展。
4. 全程保持 observe-only 为默认安全态。

| 阶段 | 主题 | 解决的 gap | 预计粒度 |
|---|---|---|---|
| **Phase 1** | Tool Registry + Policy Guard + 执行闭环 | G1 / G2 / G3 | 详见第五节 |
| **Phase 2** | Watcher / Safety Critic + 熔断 | G4 | 1 个旁路 Agent + 熔断服务 + 接入编排器 |
| **Phase 3** | Pipeline-as-Code | G5 | YAML playbook + 轻量 pipeline engine，抽离硬编码编排 |
| **Phase 4** | 推理质量：LLM 假设树 + 拓扑降噪 + 自治分级 L0–L5 | G7 | insight agent LLM 化、拓扑衍生告警归并、显式自治等级 |
| **Phase 5** | Memory 语义检索（pgvector） | G6 | 可选，按数据规模启动 |

Phase 2–5 的任务清单概要见第六节；每阶段开工前会先读完相关现有代码、产出 TODO 清单，再逐文件实现。

---

## 五、Phase 1 详细设计：Tool Registry + Policy Guard + 执行闭环

### 5.1 目标

1. 建立统一的 **Tool Registry**：所有"会对外部系统产生动作"的能力都登记，声明风险等级与约束。
2. 建立 **Policy Guard**：在"计划 → 执行"之间插入一道可审计的策略门（GPT 的"5 道门"落地）。
3. **接通执行闭环**：让 `RemediationPlan` 能真正流转到 `ExecutionRun` → 受控执行 → 审计 → 触发已有的 `verify-readonly`。
4. 默认只放行 observe-only 只读动作；高危动作一律走审批或拦截。

### 5.2 现状问题（开工前必须正视）

- `ExecutionRun` 无人创建；`execution_engine.execute_action` 无人调用；executors 未注册 → 整条执行链是死代码。
- 执行门控仅靠 `autonomous_remediation_agent` 一句硬编码 + `execution_engine` 内一段失效的 observe-only 判断。
- `policy_matcher` 只服务"触发"，不服务"执行治理"，二者概念要分清，不要混用。

### 5.3 文件清单

**新增**

| 文件 | 职责 |
|---|---|
| `backend/tools/__init__.py` | 包初始化 |
| `backend/tools/base.py` | `ToolRequest` / `ToolResult` 契约（统一执行器 I/O 形态） |
| `backend/tools/registry.py` | `ToolSpec` 数据类 + `ToolRegistry`（加载 catalog、按 tool_id 查询、校验参数） |
| `backend/tools/catalog.yaml` | 声明式工具目录（风险等级、命令白/黑名单、审批要求、超时） |
| `backend/policies/__init__.py` | 包初始化 |
| `backend/policies/schemas.py` | `RiskLevel` 枚举、`GateResult`、`PolicyDecision` 数据类 |
| `backend/policies/rules.py` | 声明式策略规则（设备分级、命令规则、变更窗口、熔断阈值），尽量复用 `services/rule_engine.py` |
| `backend/policies/guard.py` | `PolicyGuard`：5 道门主流程，输出 `PolicyDecision` |
| `backend/services/execution_service.py` | **执行闭环核心**：`execute_plan(db, plan_id)` → 逐 action 过 Guard → 受控执行 → 建 `ExecutionRun` + 审计 → 触发验证 |
| `backend/scripts/seed_tool_catalog.py` | 初始化/校验工具目录与策略规则（可选，便于运维） |

**修改**

| 文件 | 改动 |
|---|---|
| `backend/api/fabric.py` | 新增 `POST /api/fabric/plans/{plan_id}/execute` 端点，调用 `execution_service.execute_plan` |
| `backend/services/execution_engine.py` | 在 `execute_action` 前置 `PolicyGuard` 校验；observe-only 判断改为由 Guard 统一裁决；保留 `RetryPolicy` |
| `backend/main.py` | `lifespan` 启动时 `register_executor` 注册三个执行器；加载 `ToolRegistry` |
| `backend/agents/autonomous_remediation_agent.py` | 用 `PolicyGuard` 预检替换硬编码 `confidence>=0.85` 门控，`execution_mode` / `approval_status` 由策略推导 |
| `backend/engines/case_orchestrator.py` | `_create_remediation_plan` 调用 Guard 预检，把 `policy_audit` / `safety_checks` 写实 |
| `backend/api/schemas/fabric.py` | 新增 execute 请求/响应 schema |

### 5.4 Tool Registry 设计

`ToolSpec`（`tools/registry.py`）核心字段：

```
tool_id            str    唯一标识，如 "ssh.show_command" / "netbox.read" / "notify.dingtalk"
name               str    展示名
category           str    network_device / api / notification / script
executor_type      str    映射到 ExecutorType（或后续扩展）
risk_level         int    0=只读安全, 1=低危, 2=中危, 3=高危, 4=破坏性
modes              list   ["observe"] / ["observe","execute"]
allowed_commands   list   命令白名单（前缀或正则），如 ["show","display","ping","traceroute"]
blocked_patterns   list   命令黑名单正则，如 ["configure","reboot","reload","shutdown","delete","undo"]
requires_approval  bool   是否强制审批（也可由 risk_level 阈值推导）
timeout            int    秒
audit              bool   是否强制写审计（默认 true）
param_schema       dict   JSON Schema，用于 Gate 1 参数校验
```

`tools/catalog.yaml` 示例（与 GPT 的 Tool Registry YAML 思路一致，落到本项目工具上）：

```yaml
tools:
  - tool_id: ssh.show_command
    name: SSH 只读命令
    category: network_device
    executor_type: script        # 经 ssh_service 通道
    risk_level: 0
    modes: [observe]
    allowed_commands: [show, display, ping, traceroute, dis]
    blocked_patterns: ['(?i)config', '(?i)reboot', '(?i)reload', '(?i)shutdown', '(?i)undo', '(?i)delete', '(?i)erase']
    requires_approval: false
    timeout: 30
    audit: true
  - tool_id: ssh.config_change
    name: SSH 配置变更
    category: network_device
    executor_type: script
    risk_level: 3
    modes: [observe, execute]
    allowed_commands: []
    blocked_patterns: []
    requires_approval: true
    timeout: 60
    audit: true
  - tool_id: notify.dingtalk
    name: 钉钉通知
    category: notification
    executor_type: notification
    risk_level: 0
    modes: [observe, execute]
    requires_approval: false
    timeout: 10
    audit: true
```

> 设计原则：Phase 1 只把 `risk_level: 0` 且 `modes:[observe]` 的工具放进可自动执行集合（只读 SSH 命令、通知）。`risk_level >= 1` 一律 `requires_approval` 或直接拦截。

### 5.5 Policy Guard 设计（5 道门）

`PolicyGuard.check(request: ToolRequest, *, case, plan, db) -> PolicyDecision`，顺序执行 5 道门，任一拒绝即短路：

| 门 | 名称 | 逻辑 | 失败动作 |
|---|---|---|---|
| 1 | Schema 校验 | `request.params` 校验 `ToolSpec.param_schema`；工具必须在 Registry 中登记 | reject: `unregistered_tool` / `invalid_params` |
| 2 | 策略匹配 | 匹配 `policies/rules.py` 中适用规则（设备分级、站点、变更窗口） | 记录命中规则，进入下一门 |
| 3 | 风险分级 | 由 `ToolSpec.risk_level` + 命令内容（黑名单命中即升级）+ 目标设备等级（核心设备 +1）计算 `effective_risk` | —— |
| 4 | 审批门 | `effective_risk >= 2` 或 `requires_approval=true` → 必须存在已 `APPROVED` 的 `RemediationPlan` / 审批记录 | reject: `approval_required` |
| 5 | observe-only / 熔断 | `automation_mode=observe_only` 且 `effective_risk>0` 且非只读 → 拦截；同一设备在窗口内 `ExecutionRun` 次数 ≥ 阈值 → 熔断 | reject: `observe_only_blocked` / `circuit_breaker` |

`PolicyDecision`（`policies/schemas.py`）：

```
allowed            bool
effective_risk     int
gate_results       list[GateResult]   每道门的 passed/reason/detail
required_approval  bool
blocked_reason     str | None
audit              dict               完整可审计快照（写入 ExecutionRun.audit_trail）
```

> 命令白/黑名单复用 `tools/catalog.yaml`；设备分级规则尽量复用 `services/rule_engine.py` 的 `ThresholdCondition/CompositeCondition`，避免重造判断引擎。熔断阈值放 `config/pipeline_thresholds.py`。

### 5.6 执行闭环接线

`services/execution_service.py` 的 `execute_plan(db, plan_id, *, triggered_by)`：

```
1. 载入 RemediationPlan，前置校验：
   - status 必须 ∈ {APPROVED}（或 DRAFT 且经 Guard 判定全部为 observe-only 只读 → 允许自动执行）
2. 载入关联 CaseRecord；plan.status → EXECUTING；case.status → EXECUTING
3. for action in plan.plan_payload["recommended_actions"]:
     a. 由 action 解析 tool_id → ToolRegistry.get(tool_id) → ToolSpec
     b. 构建 ToolRequest（含目标设备、命令/参数、credential 解析）
     c. decision = PolicyGuard.check(request, case=case, plan=plan, db=db)
     d. if not decision.allowed:
          创建 ExecutionRun(status=FAILED, error=decision.blocked_reason, audit_trail=[decision.audit])
          按策略：拦截即停 or 跳过该 action
        else:
          execution_engine.execute_action(...) 经对应 executor 执行
          创建 ExecutionRun(status=SUCCEEDED/FAILED, request_payload, result_payload, audit_trail)
4. 全部成功 → plan.status=SUCCEEDED；case.status=VERIFYING
   存在失败 → plan.status=FAILED；case.status=ESCALATED
5. 对每个 SUCCEEDED 的 ExecutionRun，调用 post_execution_verification_service.verify_execution_readonly
6. 返回执行汇总（execution_run_ids、各 action 的 PolicyDecision 摘要）
```

`POST /api/fabric/plans/{plan_id}/execute` → 直接代理到 `execute_plan`。`main.py` 的 `lifespan` 中注册三个执行器并加载 `ToolRegistry`。

### 5.7 Phase 1 任务清单（已完成）

- [x] T1.1 `tools/base.py`：定义 `ToolRequest` / `ToolResult`
- [x] T1.2 `tools/registry.py`：`ToolSpec` + `ToolRegistry`（加载/查询/参数校验）
- [x] T1.3 `tools/catalog.json`：登记现有工具（ssh 只读、ssh 配置变更、钉钉通知、api、script、人工复核）
- [x] T1.4 `policies/schemas.py`：`RiskLevel` / `GateResult` / `PolicyDecision`
- [x] T1.5 `policies/rules.py`：设备分级 / 命令规则 / 变更窗口 / 熔断阈值
- [x] T1.6 `policies/guard.py`：5 道门主流程
- [x] T1.7 `services/execution_service.py`：`execute_plan` 执行闭环
- [x] T1.8 修改 `execution_engine.py`：注册执行器入口，执行前由 Guard 裁决
- [x] T1.9 修改 `main.py`：启动注册执行器 + 加载 Registry
- [x] T1.10 修改 `api/fabric.py` + `api/schemas/fabric.py`：新增 `execute` 端点与 schema
- [x] T1.11 修改 `autonomous_remediation_agent.py`：输出 Guard / autonomy 可判定的元数据
- [x] T1.12 修改 `case_orchestrator`：写实 `policy_audit` / `safety_checks`
- [x] T1.13 目录/规则初始化与自检：通过 `ToolRegistry` 加载 `catalog.json`
- [x] T1.14 验证：本地 `pytest` 通过

### 5.8 Phase 1 验收标准

- [x] observe-only / autonomy 模式下，允许的低风险动作可产生 `ExecutionRun(SUCCEEDED)` 并触发 `verify-readonly`。
- [x] observe-only 模式下，含配置变更（`risk_level>=1`）的动作被 Gate 5 拦截，产生 `ExecutionRun(FAILED, reason=observe_only_blocked)` 且审计完整。
- [x] 未审批的高危计划调用 `execute`，被 Gate 4 拦截（`approval_required`）。
- [x] 黑名单命令（如 `reboot`）即使工具 `risk_level=0` 也被 Gate 3 升级风险并拦截。
- [x] 同一设备窗口内执行次数超阈值触发 Gate 5 熔断。
- [x] 每个 `ExecutionRun.audit_trail` 包含完整的 PolicyDecision 快照。
- [x] 现有主链路（采样 → Case → 计划）不受影响，回归通过。

> 说明：当前环境无法连通 PostgreSQL / ELK / Zabbix / NetBox，Phase 1 实现以"代码 + 单元级可测试"为准，集成验证需在你本地带依赖环境执行。实现时会为 Guard、Registry 配套纯函数单测。

---

## 六、Phase 2–5 任务清单状态

### Phase 2 — Watcher / Safety Critic（G4）已完成
- [x] `agents/safety_critic_agent.py`：旁路审查 Agent，检查证据充分性、置信度、动作越界与补证据需求。
- [x] 熔断与频率控制：由 `PolicyGuard` + `pipeline_thresholds.py` 在执行前统一裁决。
- [x] 接入 `case_orchestrator`：在 remediation 之后运行 Critic；Critic 否决时 Case 转 `ESCALATED`。
- [x] 新增 `AgentType.SAFETY_CRITIC` 并在 `init_db()` 中兼容历史 PostgreSQL 枚举。

### Phase 3 — Pipeline-as-Code（G5）已完成
- [x] `pipelines/schemas.py`：playbook / step / state 数据契约。
- [x] `pipelines/engine.py`：轻量 pipeline 引擎，支持 agent、hook、loop、predicate。
- [x] `pipelines/definitions/*.json`：默认、关键事件、日志轻量三类 playbook。
- [x] `case_orchestrator.run_case_pipeline`：改为按 case 属性选择 playbook，保留默认兜底流程。

### Phase 4 — 推理质量（G7）已完成
- [x] `insight_analysis_agent`：输出 hypothesis tree，并兼容旧 root_cause 字段。
- [x] `services/topology_correlation_service.py`：基于 NetBox 拓扑做衍生告警归并与 evidence 关联。
- [x] 自治分级 L0–L5 显式化：`automation_settings_service` 统一读写，`PolicyGuard` 按等级放行。

### Phase 5 — Memory 语义检索（G6）已完成
- [x] `MemoryEntry.embedding`：以 JSON float array 存储向量，保持 PostgreSQL 兼容和后续 pgvector 迁移空间。
- [x] `services/embedding_service.py`：可选 OpenAI 兼容 embedding，失败降级，不阻断主流程。
- [x] `services/memory_retriever.py`：语义召回补充关键词和元数据召回。
- [x] Case pipeline 按 signal family / 任务上下文检索历史记忆。

### 当前本地验收
- [x] 后端单元测试：`pytest`，136 passed。
- [x] 前端生产构建：`npm run build`，通过。
- [ ] Docker Compose 一键启动：本次补齐并验证。

---

## 七、附录：开工前待确认问题

实现 Phase 1 时需先读以下文件确认细节，避免设计偏差：

1. `services/remediation_recommendation_service.py` —— `build_actions` 的输出结构、`last_policy_audit` 的内容（决定 `recommended_actions` 里 action 的字段形态，直接影响 `execution_service` 如何解析出 tool_id）。
2. `services/ssh_service.py` —— `execute_commands` 的精确契约、是否已有只读约束、`build_diagnostic_commands` 的命令集（决定 `ssh.show_command` 工具的 param_schema 与白名单）。
3. `scripts/config_automation_policies.py` + `models/automation.py:AutomationPolicy` —— 现有 `AutomationPolicy` 表如何 seed，Policy Guard 的规则是否要与之打通/复用，避免两套策略概念冲突。
4. `agents/insight_analysis_agent.py` / `alert_triage_agent.py` —— 是否已调用 `llm_client`（影响 Phase 4 范围判断）。
5. `api/cases.py` / `api/agents.py` —— 是否已有手动触发 pipeline / 重跑的端点（执行端点的命名与风格要对齐）。

---

*本文档为评审与计划，不含代码改动。确认无误后从 Phase 1 任务清单 T1.1 开始逐项实现，每项产出代码 + 必要单测，并在实现前用 TodoList 跟踪进度。*
