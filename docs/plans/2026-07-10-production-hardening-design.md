# AgenticOps 生产级加固设计

**日期**：2026-07-10  
**目标规模**：3000 台以内网络设备、ELK 日志约 10 万条/日、单审批人为主  
**目标运行模式**：多 Agent 自动只读采证，所有状态变更必须登录审批后执行

## 1. 结论与范围

现有项目具备可延续的领域基础：统一事件、Case、Evidence、AgentRun、AgentClaim、RemediationPlan、ExecutionRun、声明式 Pipeline、Safety Critic、工具目录和策略门控均已存在。生产化不应重建第二套 Agent Runtime，而应加固现有链路的身份、安全、可靠性、观测有效性和工程治理。

当前版本不满足生产准入，主要阻塞项包括：

- 审批、执行、SSH 凭据和系统设置接口缺少认证与授权。
- 审批人、执行人由客户端字段提供，无法形成可信审计身份。
- 执行缺少严格状态迁移、方案冻结、幂等键和并发锁。
- Webhook URL 可由动作参数传入，存在 SSRF、密钥泄露和投递不可追踪风险。
- 执行后验证没有比较变更前后的目标信号，可能错误关闭 Case。
- 多 Agent Pipeline 当前不自动执行 SSH 只读采证；通用命令接口又绕过策略门控。
- ELK 定时采样有单次 1000 条限制，没有可靠游标、分页和缺口检测。
- 数据库依赖启动时 `create_all` 与手写 DDL，缺少正式迁移和回滚能力。
- 后台任务与 API 进程耦合，监控、CI 和生产集成测试不足。

## 2. 核心安全原则

1. **只读采证可自动执行**：Agent 可以自动登录设备采集状态，但不能直接提交原始命令。
2. **所有状态变更必须审批**：配置修改、接口启停、清理状态、重启、文件上传和脚本执行均绑定有效审批。
3. **命令属性由平台决定**：只读与变更属性由预定义能力和厂商模板确定，不能信任 Agent 声明的 `read_only` 字段。
4. **证据不足不得自动闭环**：数据源缺失、不新鲜或验证不充分时只能得到 `INCONCLUSIVE`。
5. **身份与方案不可抵赖**：审批绑定登录身份、冻结后的方案版本、目标设备、确切动作、有效期和哈希。
6. **默认拒绝**：身份源、工具、策略、命令分类或验证规则异常时 fail closed。

## 3. 总体架构

核心业务链路：

```text
ELK 游标采集
  -> 聚合 / 指纹去重 / 事件路由 / 拓扑归并
  -> Case
  -> Multi-Agent 分析
  -> 自动只读 Probe 补采证据
  -> 方案生成与 Safety Critic
  -> 冻结方案版本
  -> Webhook: approval.requested
  -> 审批人通过 SSO/本地账号登录审批
  -> 幂等执行
  -> 多轮只读验证
  -> VERIFIED / INCONCLUSIVE / REGRESSED
  -> Webhook: verification.completed
```

部署分为两类进程：

- **API**：处理 Web、认证、查询、审批和执行请求受理，不运行周期采集任务。
- **Worker**：处理 ELK 采集、Agent Pipeline、只读 Probe、Webhook Outbox、执行任务和延迟验证。

首期使用 PostgreSQL Outbox、`FOR UPDATE SKIP LOCKED` 和 Advisory Lock 实现可靠任务抢占及多实例互斥，不强制引入 Redis。后续吞吐需要提升时，可在保持领域接口不变的前提下替换队列实现。

## 4. 双通道设备访问模型

### 4.1 自动只读 Probe 通道

Agent 只能申请结构化 Probe，不允许生成或提交任意 SSH 命令。首期能力包括：

- `interface.summary`
- `interface.errors`
- `routing.neighbors`
- `system.resources`
- `recent.logs`
- `running_config.redacted`

Probe Gateway 根据 NetBox 中的厂商、平台和版本选择固定命令模板，校验参数，执行命令，限制输出，完成脱敏后写入 EvidenceItem。每次执行记录 AgentRun、Probe ID、命令模板版本、目标设备、耗时、结果摘要、输出哈希和失败原因。

安全约束：

- 优先使用设备侧只读账号，并通过 TACACS+/RADIUS 做命令授权。
- 每台设备并发默认 1，全局并发默认 30，支持站点级限速。
- 禁止命令拼接、管道、重定向、交互式 Debug 和未注册参数。
- 配置输出在进入数据库或 LLM 前清除密码、密钥、团体字、Token 等敏感值。
- SSH 必须使用已登记 Host Key，禁止自动信任未知主机。
- 设置连接超时、命令超时、输出上限、熔断和取消机制。

### 4.2 审批后变更通道

以下动作必须审批：配置模式、接口状态变更、路由或策略修改、清除状态、重启、文件上传、任意脚本及其他可能改变外部状态的 API。

审批对象包含：

- 冻结的方案版本和 SHA-256 哈希
- 目标设备集合
- 确切命令或结构化变更动作
- 风险等级和 Safety Critic 结果
- 预期结果和验证规则
- 回滚方案
- 审批人身份和审批有效期

任何审批后修改都会生成新版本并使旧审批失效。现有任意命令接口必须移除，或限制为受认证管理员的审批后变更入口，不能继续绕过 Tool Registry 和 Policy Guard。

## 5. 身份认证、SSO 与权限

认证采用可插拔 Provider，同一部署允许启用多个身份源：

- `LocalProvider`：本地账号，用于独立部署和应急恢复。
- `OIDCProvider`：原生 SSO，适配 Keycloak、Microsoft Entra ID、Okta、Auth0、Dex 等。
- `LDAPProvider`：适配 LDAP 和 Active Directory 直接认证。
- `SAMLProvider`：适配仅提供传统 SAML 2.0 的企业身份平台。

统一 Provider 输出内部身份，使用 `(provider_id, external_subject)` 唯一绑定用户。OIDC 使用 Authorization Code + PKCE，并校验 `state`、`nonce`、issuer 和 audience；SAML 校验签名、issuer、audience、时间窗口和 InResponseTo。LDAP 必须使用 TLS。

Web 登录使用服务端 Session Cookie，设置 `HttpOnly`、`Secure` 和合适的 `SameSite`，所有状态变更接口启用 CSRF 防护。机器接入使用独立 API Token，机器 Token 无权审批或执行设备变更。

首期角色：

- `viewer`：查看 Case、证据和执行结果。
- `operator`：触发只读 Probe、发起审批。
- `approver`：批准或拒绝冻结后的方案。
- `executor`：提交已批准方案的执行请求。
- `admin`：管理身份源、用户、凭据、Webhook 和安全策略。

同一用户可同时拥有 `approver` 和 `executor`，满足当前单审批人场景；两类动作仍分别审计，以便后续启用职责分离。IdP/LDAP 组支持映射到内部角色。

## 6. 审批与执行状态机

主状态流：

```text
DRAFT
  -> PENDING_APPROVAL
  -> APPROVED
  -> EXECUTING
  -> VERIFYING
  -> SUCCEEDED
```

异常终态或分支包括：`REJECTED`、`EXPIRED`、`CANCELLED`、`FAILED`、`REGRESSED`、`INCONCLUSIVE`。

规则：

- 发起审批时冻结方案并生成哈希。
- 审批必须引用准确的方案版本；过期审批不能执行。
- 执行请求必须携带幂等键。
- 执行前对 RemediationPlan 加数据库行锁，并使用唯一约束保证同一方案版本只能成功创建一个执行任务。
- Worker 领取任务后再次校验审批、哈希、策略、设备范围和执行窗口。
- 每个动作单独记录请求、策略裁决、执行结果和回滚结果。
- 部分失败不得被汇总为成功；系统进入 `FAILED` 或 `REGRESSED` 并通知人工处置。

## 7. 通用 Webhook

Webhook 是系统级出站事件能力，不是 Agent 自由选择 URL 的执行工具。Endpoint 由管理员预配置，业务只能引用 Endpoint ID。

首期事件：

- `case.created`
- `evidence.ready`
- `approval.requested`
- `approval.decided`
- `execution.started`
- `execution.completed`
- `verification.completed`

可靠性与安全：

- 业务状态和 OutboxEvent 在同一数据库事务内写入。
- Worker 使用指数退避、最大重试、死信和人工重投。
- 每条事件带唯一 `event_id`，接收方可幂等去重。
- 使用 HMAC-SHA256 对时间戳和原始请求体签名，限制可接受时间窗口。
- 只允许 HTTPS；配置和投递时都阻止回环、私网、链路本地和云元数据地址。
- DNS 每次投递重新解析并校验，禁止跨安全边界重定向。
- URL 与 Secret 加密保存，不进入 Agent 上下文、应用日志或普通 API 响应。
- 投递日志记录 Endpoint ID、事件 ID、尝试次数、HTTP 状态、耗时和脱敏错误。

Webhook 仅用于通知，不能通过匿名回调批准方案。审批必须由登录用户在 Web 页面完成。

## 8. 观测有效性与验证闭环

每个可执行动作必须携带结构化验证规则，描述目标对象、基线查询、预期变化、等待时间、最大观测窗口和强制数据源。

执行前保存：

- 触发该 Case 的原始事件和告警标识
- 相关 Zabbix Problem 状态及关键指标
- 目标接口、邻居、资源等设备状态
- 相关日志签名、频率和时间窗口
- 数据采集时间与新鲜度

执行后按可配置周期验证，例如立即、2 分钟、5 分钟。验证比较同一对象和同一信号的前后状态，而不是使用全局告警数量。

判定：

- `VERIFIED`：全部强制检查通过，目标信号恢复且没有关联退化。
- `INCONCLUSIVE`：数据源不可用、不新鲜、对象无法定位或证据不足。
- `REGRESSED`：目标指标恶化、原告警升级或出现新的关联严重告警。

只有 `VERIFIED` 才允许 Case 自动进入 `RESOLVED`。`INCONCLUSIVE` 和 `REGRESSED` 必须保持 Case 打开并发送 Webhook 通知。

## 9. ELK 聚合与告警降噪

ELK 采集改为基于稳定时间字段和文档 ID 的游标分页；每个 Scope 保存 checkpoint、最近成功时间、查询窗口、读取数量和缺口状态。Worker 重启后从 checkpoint 恢复，不依赖固定 1000 条上限。

降噪顺序：

1. 标准化字段与日志签名。
2. 时间窗内同设备同签名去重。
3. 同类信号聚类与频率阈值升级。
4. ELK 与 Zabbix 跨源关联。
5. NetBox 拓扑衍生告警归并。
6. 将被归并信号作为证据附着到父 Case，不静默丢弃。

所有规则输出 reason、版本、输入统计和 confidence，支持离线回放。上线前至少运行两周 Shadow Mode，与人工标注结果对照。

## 10. 工程模块与数据迁移

目标模块：

- `auth/`：Provider、Session、RBAC、组映射和审计。
- `probes/`：只读能力目录、厂商模板、SSH Gateway、脱敏。
- `approvals/`：版本冻结、哈希和审批状态机。
- `executions/`：幂等执行、设备锁、回滚和熔断。
- `webhooks/`：Endpoint、Outbox、签名、投递和死信。
- `verifications/`：基线、规则、多轮观测和判定。
- `ingestion/`：ELK checkpoint、分页、聚合和降噪。

渐进拆分 `api/events.py`、`services/log_sampler.py` 和 `engines/case_orchestrator.py`，保留现有模型和 Pipeline 行为，避免大爆炸式改写。

引入 Alembic 正式迁移：

- 为现有生产数据库生成基线版本。
- 所有新表、索引、枚举和约束通过版本化迁移管理。
- 移除启动路径中的业务 DDL；应用启动只检查迁移版本，不自动修改生产库。
- 每个迁移提供前向验证，并为不可逆变更提供明确备份和恢复步骤。

## 11. 可观测性

提供结构化日志、指标和追踪关联 ID。关键指标包括：

- ELK checkpoint 延迟、每批读取数、缺口和失败率
- 原始事件数、去重数、聚类数、Case 数和各 disposition 比例
- Agent 成功率、耗时、降级次数、证据缺口和模型调用错误
- Probe 成功率、每设备并发、超时和熔断
- 审批等待时间、过期数和拒绝数
- 执行成功率、重复请求拦截数和回滚次数
- Webhook 投递延迟、重试、失败和死信数
- 验证结果分布、新鲜度失败和错误闭环拦截数

`/health/live` 仅检查进程存活；`/health/ready` 检查数据库迁移版本和关键依赖；外部 ELK、NetBox、Zabbix、身份源的状态作为单独 dependency health 暴露，避免非关键依赖短暂故障导致进程重启风暴。

## 12. 测试与生产准入

测试分层：

- 单元测试：Probe 分类、命令模板、脱敏、签名、状态机、角色映射和验证规则。
- PostgreSQL 集成测试：迁移、并发审批、幂等执行、Outbox 抢占和锁。
- 身份集成测试：Local、OIDC、LDAP、SAML 的登录、登出、组映射和失效。
- 安全测试：审批绕过、SSRF、重放、CSRF、越权、命令拼接和敏感信息泄露。
- 端到端测试：事件进入、Agent 自动采证、Webhook 通知、Web 审批、单次执行和多轮验证。
- 压力与恢复测试：日均 10 万条及至少 3 倍突发、Worker 重启、Webhook 长时间失败和数据源短暂不可用。

初始生产门槛：

- 重复事件减少至少 80%。
- 已标注的严重事件不得自动归为噪声。
- 数据源缺失或不新鲜时，Case 自动关闭数必须为 0。
- 未审批状态变更执行数必须为 0。
- 同一幂等键导致多次设备变更的数量必须为 0。
- Webhook URL/Secret、设备密码、密钥及未脱敏配置泄露数量必须为 0。

以下任一情况阻断发布：未审批变更可执行、重复请求造成重复执行、身份或角色可绕过、Webhook SSRF、Secret 泄露、验证证据不足却关闭 Case、数据库迁移不可重复执行。

## 13. 首期交付边界

首期同时交付：

1. Local、OIDC、LDAP/AD、SAML Provider 与 RBAC。
2. 自动只读 Probe Gateway、厂商命令模板、Host Key 校验和脱敏。
3. 方案冻结、审批状态机、幂等执行和不可变审计。
4. 通用 Webhook Outbox、HMAC 签名、重试、死信和重投。
5. 基线与多轮验证，支持 `VERIFIED / INCONCLUSIVE / REGRESSED`。
6. ELK checkpoint、分页聚合、降噪回放和 Shadow Mode 指标。
7. API/Worker 分离、Alembic、CI、生产集成测试和可观测性。

首期不建设通用分布式多 Agent 平台，不增加与当前规模无关的复杂消息基础设施，也不允许 Agent 自由生成设备命令。
