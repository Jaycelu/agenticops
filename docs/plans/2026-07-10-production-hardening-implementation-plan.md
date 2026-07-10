# AgenticOps 生产级加固实施计划

**设计依据**：`docs/plans/2026-07-10-production-hardening-design.md`  
**交付策略**：按安全边界优先、每阶段可独立验证、保持现有领域模型与 Pipeline 的方式渐进改造。

## 总体验收条件

- 自动只读 Probe 无需审批，但 Agent 不能提交原始命令。
- 任何改变设备或外部系统状态的动作都必须绑定有效审批。
- Local、OIDC、LDAP/AD、SAML 可配置并存，审批身份来自服务端 Session。
- 通用 Webhook 使用 Outbox、签名、重试和死信，URL 不来自 Agent 动作。
- 执行前后基于同一目标信号验证；证据不足不关闭 Case。
- ELK 采集使用 checkpoint 与分页，Worker 重启后无静默缺口。
- PostgreSQL 迁移、CI、集成测试和安全回归测试成为发布门禁。

## Phase 0：测试与迁移基线

### 任务

1. 确认当前工作区删除 `backend/tests/`、`backend/pytest.ini` 及测试依赖是否为预期变更。
2. 拆分运行依赖和开发依赖：
   - `backend/requirements.txt`
   - `backend/requirements-dev.txt`
3. 建立 GitHub Actions：后端单元测试、PostgreSQL 集成测试、前端构建、迁移检查和安全静态检查。
4. 初始化 Alembic 配置与当前模型基线迁移。
5. 将 `database.init_db()` 的运行时 DDL 改成只验证迁移版本；保留显式开发初始化命令。

### 验证

- 全新 PostgreSQL 能从空库升级到 head。
- 从当前 schema 快照执行 stamp/upgrade 不破坏数据。
- 连续执行迁移不会产生额外变更。
- CI 在未运行迁移、测试失败或前端构建失败时阻断。

## Phase 1：认证、SSO、RBAC 与审计

### 新增组件

- `backend/auth/models.py`：User、IdentityProvider、ExternalIdentity、RoleBinding、Session、ApiToken。
- `backend/auth/providers/base.py`：统一 Provider 接口。
- `backend/auth/providers/local.py`
- `backend/auth/providers/oidc.py`
- `backend/auth/providers/ldap.py`
- `backend/auth/providers/saml.py`
- `backend/auth/service.py`：登录、回调、Session、登出和组映射。
- `backend/auth/dependencies.py`：`current_user`、`require_permissions`。
- `backend/audit/models.py` 与 `backend/audit/service.py`：追加式安全审计。
- `backend/api/auth.py`：登录入口、Provider 列表、回调和 Session 查询。

### 修改范围

- 为审批、执行、Webhook、SSH 凭据、集成配置、自动化模式和用户管理接口增加权限依赖。
- 删除请求体中的可信 `approver`、`initiator`、`triggered_by`、`reviewer` 语义，统一从 Session 注入。
- 对浏览器状态变更接口增加 CSRF 验证。
- 对事件接入等机器接口使用权限受限的 API Token。

### 验证

- 匿名用户不能访问敏感查询或任何状态变更接口。
- OIDC 校验 PKCE/state/nonce/issuer/audience。
- SAML 校验签名、InResponseTo、issuer、audience 和时间窗口。
- LDAP 只允许 TLS 连接。
- IdP 组映射能授予和撤销内部角色。
- 用户、角色和 Provider 变更均写入审计。

## Phase 2：自动只读 Probe Gateway

### 新增组件

- `backend/probes/schemas.py`：ProbeRequest、ProbeResult、EvidenceEnvelope。
- `backend/probes/catalog.py`：Probe 能力和参数 schema。
- `backend/probes/templates/`：按厂商/平台维护只读命令模板。
- `backend/probes/gateway.py`：模板解析、限流、设备锁、超时和审计。
- `backend/probes/redaction.py`：配置、日志和命令输出脱敏。
- `backend/probes/ssh_transport.py`：Host Key 校验与只读 SSH 传输。
- `backend/models/probe.py`：ProbeRun、DeviceHostKey、ProbeTemplateVersion。

### 修改范围

- `case_orchestrator` 通过 Probe ID 补采证据，不再直接调用 `ssh_service.execute_commands`。
- `ssh.show_command` 改为 Probe Gateway 能力；Agent 不接触最终命令。
- 移除或封闭 `/api/ssh/execute-commands` 任意命令入口。
- SSH 凭据绑定设备与只读能力范围。

### 验证

- 所有注册 Probe 在支持的平台上只能产生已批准模板中的命令。
- 命令拼接、管道、重定向、换行注入和未知参数全部拒绝。
- 未登记 Host Key、只读账号授权失败或输出超限时 fail closed。
- 敏感配置在写库及发送给 LLM 前完成脱敏。
- 单设备并发不超过 1，全局并发限制可配置。

## Phase 3：方案冻结、审批和幂等执行

### 新增组件

- `backend/approvals/service.py`：方案规范化、版本冻结、哈希、审批和过期。
- `backend/models/approval.py`：PlanVersion、ApprovalDecision。
- `backend/executions/service.py`：任务受理、行锁、幂等、执行与回滚。
- `backend/models/execution_job.py`：ExecutionJob、ExecutionActionResult、IdempotencyRecord。

### 修改范围

- 重写 `fabric_plan_service`，使审批状态迁移由领域服务统一管理。
- `execute_plan` 只受理冻结且已批准、未过期的方案版本。
- 请求体不再接受执行人身份。
- Worker 执行前再次验证方案哈希、权限、策略和执行窗口。
- Tool Registry 按 capability 分类只读和 mutation；不再信任动作中的 `mode`。

### 验证

- 方案审批后任何字段变化都会使审批失效。
- 相同幂等键或并发执行请求最多产生一次设备变更。
- 未审批、已拒绝、已过期或哈希不匹配的方案不能执行。
- 部分失败、回滚失败和策略拒绝不会被汇总为成功。
- 审批、执行和回滚均记录服务端身份与完整审计链。

## Phase 4：通用 Webhook Outbox

### 新增组件

- `backend/webhooks/models.py`：WebhookEndpoint、OutboxEvent、WebhookDelivery。
- `backend/webhooks/service.py`：事件创建、payload 版本和脱敏。
- `backend/webhooks/security.py`：URL 校验、DNS/IP 校验和 HMAC 签名。
- `backend/webhooks/worker.py`：抢占、投递、退避、死信和人工重投。
- `backend/api/webhooks.py`：Endpoint 管理、测试、投递查询和重投。

### 修改范围

- Case、审批、执行和验证状态变化在同一事务内创建 OutboxEvent。
- 删除 `notification_executor` 对动作中 `webhook_url` 的信任。
- Endpoint Secret 使用应用密钥加密，API 只显示指纹和更新时间。

### 验证

- 业务事务回滚时不产生可投递事件。
- Worker 崩溃、超时或 5xx 后可安全重试，不重复创建业务事件。
- 私网、回环、链路本地、云元数据地址和不安全重定向全部拒绝。
- HMAC 签名、时间戳与 event_id 可被测试接收端验证。
- URL、Secret 和敏感业务字段不出现在日志或普通 API 响应。

## Phase 5：可信验证闭环

### 新增组件

- `backend/verifications/schemas.py`：VerificationPolicy、CheckDefinition、CheckResult。
- `backend/verifications/baseline.py`：执行前基线采集。
- `backend/verifications/service.py`：多轮调度、同对象对比和判定。
- `backend/models/verification.py`：VerificationRun、VerificationCheck、BaselineSnapshot。

### 修改范围

- RemediationPlan 的每个 mutation action 必须声明验证规则。
- 执行 Worker 在变更前完成强制基线；基线失败则阻止执行。
- 替换当前按总告警数判断恢复的逻辑。
- 只有 VERIFIED 可以自动关闭 Case。

### 验证

- 原始告警仍存在时不能判定 VERIFIED。
- 数据源不可用、数据过期或对象不一致时返回 INCONCLUSIVE。
- 指标恶化或新增关联严重告警时返回 REGRESSED。
- 多轮验证可在 Worker 重启后继续执行。
- 所有结果包含基线、观测值、数据新鲜度和判定理由。

## Phase 6：ELK checkpoint、聚合与降噪评测

### 新增组件

- `backend/ingestion/checkpoints.py`：Scope checkpoint 与租约。
- `backend/ingestion/elk_reader.py`：稳定排序、分页、重试和缺口检测。
- `backend/ingestion/aggregation.py`：签名、时间窗聚合和去重。
- `backend/ingestion/replay.py`：离线数据集回放与规则版本评测。

### 修改范围

- 从 `log_sampler.py` 抽离调度、读取、聚合和入库职责。
- Worker 通过数据库租约运行 Scope 任务，API 进程不启动采样器。
- 将事件规则版本、命中理由和输入统计写入决策快照。
- 拓扑归并继续保留 EvidenceItem，不静默丢弃衍生信号。

### 验证

- 读取超过 1000 条的窗口时无遗漏且无重复入库。
- 同时间戳文档通过文档 ID 稳定排序。
- Worker 在任意页崩溃后能从 checkpoint 恢复。
- 3 倍突发负载下 checkpoint 延迟可控。
- Shadow Mode 报告重复减少率、严重事件误降噪数和 Case 压缩率。

## Phase 7：模块拆分、可观测性与发布门禁

### 任务

1. 将 `api/events.py` 拆成摄取、查询、关系和统计路由。
2. 将 `case_orchestrator.py` 拆成上下文采集、Agent 执行、计划生成和状态收口服务。
3. 统一错误类型与 API 错误响应，移除关键路径的宽泛静默捕获。
4. 增加结构化日志、关联 ID、Prometheus 指标和依赖健康检查。
5. 更新 Docker Compose 为 API + Worker，并补充生产部署和回滚文档。

### 验证

- `/health/live` 不依赖外部服务；`/health/ready` 验证数据库和迁移状态。
- ELK、NetBox、Zabbix、身份源分别暴露依赖状态。
- 关键链路能通过 case_id、agent_run_id、execution_job_id 和 event_id 关联。
- 发布检查覆盖迁移、测试、安全门禁、备份和回滚演练。

## 实施顺序与检查点

1. Phase 0 完成后建立可靠测试与迁移地基。
2. Phase 1 完成后，先关闭所有匿名敏感接口。
3. Phase 2 完成后，在 observe-only 环境启用 Agent 自动采证。
4. Phase 3–5 完成前，设备 mutation 保持全局禁用。
5. Phase 4 完成后启用审批与验证通知。
6. Phase 6 完成后运行至少两周 Shadow Mode。
7. 所有生产门槛通过后，才允许审批后的设备变更。

每个 Phase 单独提交、单独评审并提供测试证据；不得用后续阶段补偿当前阶段的安全缺口。
