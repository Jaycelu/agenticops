# 生产部署、恢复与放量

首次安装、旧库接管和管理员初始化请先执行根目录 [DEPLOYMENT.md](../DEPLOYMENT.md)。本文只描述生产运行责任，不重复安装步骤。

## 1. 运行拓扑边界

生产只创建一个 PostgreSQL 逻辑数据库 `netops_agenticops`，认证、审批、执行、Webhook、ELK checkpoint、Agent Graph/Checkpoint 和审计表共用该库。CI 的测试库是隔离资源，不属于生产拓扑。
API 只受理和查询 Graph Job，独立 Worker 负责推进；迁移是一次性任务，不能由多个 API 实例并发执行。首次部署保持 `AUTOMATION_OBSERVE_ONLY=true`。不要把 PostgreSQL 端口暴露到公网；Compose 默认只绑定 `127.0.0.1`。

## 2. 集成验收

- SSO：为 OIDC、LDAP/AD 或 SAML 建立身份源，验证登录、禁用用户、组到角色映射和紧急本地账号。
- 设备：导入 SSH host key；基础检查只能使用 Probe Catalog 中的只读命令，任意命令接口永久关闭。变更命令必须走冻结计划和人工审批。
- Webhook：接收方按原始 body 验证 HMAC，按事件 ID 幂等，拒绝过期时间戳；测试退避、死信、重投。
- ELK：代理必须返回稳定唯一 document ID，并支持按时间戳和 ID 的升序 `search_after`。无法保证时采集器会拒绝推进 checkpoint。
- 观测：采集 `/metrics`，对 Worker 不存活、checkpoint lag、Webhook dead、待验证积压和执行中任务设置告警。

建议至少建立以下告警：

| 信号 | 建议条件 | 处理 |
| --- | --- | --- |
| `agenticops_worker_alive` | 连续 2 分钟为 `0` | 停止放量，检查 Worker 日志和数据库 |
| `agenticops_elk_checkpoint_lag_seconds` | 超过业务允许延迟并持续 10 分钟 | 检查 ELK、分页契约和 Worker 吞吐 |
| `agenticops_webhook_deliveries_dead` | 大于 `0` | 检查接收端后人工重投 |
| `agenticops_webhook_deliveries_pending` | 持续增长 | 检查 DNS、TLS、限流和接收端容量 |
| `agenticops_verifications_pending` | 超过验证窗口仍增长 | 禁止继续扩大变更范围 |
| `agenticops_execution_jobs_running` | 超过动作超时仍未下降 | 检查设备锁和执行记录，禁止盲目重试 |
| `agent_tool_call_failures_total` | 短时间持续增长 | 检查 Tool Registry、PolicyGuard、凭据和 Probe 输出解析 |
| `agent_budget_exhausted_total` | 任一资源持续增长 | 检查诊断是否无法收敛，不要直接放大预算 |
| `case_graph_resume_total` | 异常增长 | 检查 Worker 重启、租约时钟和数据库连接稳定性 |
| `human_escalation_total` | 超出业务基线 | 检查凭据缺失、证据冲突和根因确认阈值 |

同时采集 `agent_task_total`、`agent_task_duration_seconds`、`agent_message_total`、`agent_tool_call_total`、`case_state_transition_total`、`hypothesis_confirmed_total` 和 `hypothesis_rejected_total`。

日志应按 `request_id`、`case_id`、`task_id`、`agent_run_id`、`tool_call_id`、`graph_node`、`correlation_id`、`execution_job_id`、`event_id` 和 Worker 名称建立检索视图。任何告警都应链接到对应 Runbook，而不是只发送无上下文通知。

## 3. 备份与恢复演练

```bash
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > netops_agenticops.dump
docker compose exec -T postgres sh -c \
  'createdb -U "$POSTGRES_USER" netops_agenticops_restore_test'
docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" --exit-on-error -d netops_agenticops_restore_test' \
  < netops_agenticops.dump
```

恢复测试应核对 Alembic revision、用户/角色、审计链、审批与执行记录、Webhook outbox、ELK checkpoint，以及 Agent Graph Run、Task、Message、Tool Call、Budget、Checkpoint、Timeline 和 Hypothesis 的数量与关联。至少选一个未完成的测试 Graph，在隔离恢复库连接测试 Worker，确认能够从持久化状态继续推进。备份文件必须加密并按组织策略保留。

## 4. 回滚

1. `docker compose stop worker backend`，防止继续采集、投递或执行。
2. 保留故障数据库和日志用于取证，不覆盖原库。
3. 恢复备份到新的空数据库，或在 schema 兼容时回退应用镜像。
4. 先启动 API 并验证 `/health/ready`，再启动 Worker。
5. 保持 observe-only，核对 outbox、checkpoint 和待验证任务后恢复入口流量。

v0.2.0 的 `0011_multi_agent_graph` downgrade 只用于隔离环境验证。生产 Graph 已写入后回滚应恢复升级前备份到新数据库，不应依赖原库原地 downgrade。回滚不得删除旧 Evidence、Claim、Timeline 或审计记录来“修复”状态。

## 5. 两周 Shadow Mode 与渐进放量

连续 14 天只生成建议、证据和审批计划，不执行设备变更。每日导出 replay/noise 报告并由运维人员标注误报和漏报。严重事件误降噪必须为 0。

通过后按低风险目录逐项放量：先单设备、可回滚、具有前后验证的动作；再扩大站点。每次只启用一个命令目录项，观察至少一个完整业务周期。任何 regressed、审计链异常、host key 不匹配或 Worker/数据库不稳定都立即回到 observe-only。
