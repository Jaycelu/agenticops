# 生产部署、恢复与放量

## 1. 单数据库部署

生产只创建一个 PostgreSQL 逻辑数据库 `netops_agenticops`，认证、审批、执行、Webhook、ELK checkpoint 和审计表共用该库。CI 的测试库是隔离资源，不属于生产拓扑。

```bash
cp deploy/docker.env.example .env
# 使用密码管理器写入 APP_SECRET_KEY、POSTGRES_PASSWORD 及外部系统凭据
docker compose config -q
docker compose pull
docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d backend worker frontend
docker compose ps
```

首次部署保持 `AUTOMATION_OBSERVE_ONLY=true`。不要把 PostgreSQL 端口暴露到公网；Compose 默认只绑定 `127.0.0.1`。

## 2. 集成验收

- SSO：为 OIDC、LDAP/AD 或 SAML 建立身份源，验证登录、禁用用户、组到角色映射和紧急本地账号。
- 设备：导入 SSH host key；基础检查只能使用 Probe Catalog 中的只读命令，任意命令接口永久关闭。变更命令必须走冻结计划和人工审批。
- Webhook：接收方按原始 body 验证 HMAC，按事件 ID 幂等，拒绝过期时间戳；测试退避、死信、重投。
- ELK：代理必须返回稳定唯一 document ID，并支持按时间戳和 ID 的升序 `search_after`。无法保证时采集器会拒绝推进 checkpoint。
- 观测：采集 `/metrics`，对 Worker 不存活、checkpoint lag、Webhook dead、待验证积压和执行中任务设置告警。

## 3. 备份与恢复演练

```bash
docker compose exec -T postgres pg_dump -U netops -d netops_agenticops -Fc > netops_agenticops.dump
createdb netops_agenticops_restore_test
pg_restore --exit-on-error --clean --if-exists -d netops_agenticops_restore_test netops_agenticops.dump
```

恢复测试应核对 Alembic revision、用户/角色、审计链、审批与执行记录、Webhook outbox、ELK checkpoint。备份文件必须加密并按组织策略保留。

## 4. 回滚

1. `docker compose stop worker backend`，防止继续采集、投递或执行。
2. 保留故障数据库和日志用于取证，不覆盖原库。
3. 恢复备份到新的空数据库，或在 schema 兼容时回退应用镜像。
4. 先启动 API 并验证 `/health/ready`，再启动 Worker。
5. 保持 observe-only，核对 outbox、checkpoint 和待验证任务后恢复入口流量。

## 5. 两周 Shadow Mode 与渐进放量

连续 14 天只生成建议、证据和审批计划，不执行设备变更。每日导出 replay/noise 报告并由运维人员标注误报和漏报。严重事件误降噪必须为 0。

通过后按低风险目录逐项放量：先单设备、可回滚、具有前后验证的动作；再扩大站点。每次只启用一个命令目录项，观察至少一个完整业务周期。任何 regressed、审计链异常、host key 不匹配或 Worker/数据库不稳定都立即回到 observe-only。
