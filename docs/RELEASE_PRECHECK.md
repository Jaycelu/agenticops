# AgenticOps 生产发布门禁

代码合并、镜像构建成功只代表“可部署”，不代表已经达到生产认证。以下门禁必须在目标服务器与真实集成环境执行并留存证据。

## 自动门禁

- 后端单元测试、PostgreSQL 集成测试与 Alembic `check` 通过。
- Alembic 从当前生产 head 升级到 `0011_multi_agent_graph`，并在隔离测试库完成 `0011 -> 0010 -> 0011` 往返。
- Ruff、Bandit、pip-audit、Python compileall 通过。
- 前端 `npm ci && npm run build` 通过。
- `APP_SECRET_KEY`、`POSTGRES_PASSWORD` 注入后 `docker compose config -q` 通过。
- API `/health/ready`、Worker heartbeat 与 `/metrics` 可被监控系统采集。
- API 根路径、前端 package metadata、README badge、Git tag 和 Release 标题版本一致。
- 不允许发布提交中存在未处理的临时标记、占位 API、空模型或静态假数据页面。

本地门禁参考命令（测试连接串只能指向隔离测试库）：

```bash
cd backend
RUN_POSTGRES_TESTS=1 pytest -q
alembic check
alembic downgrade 0010
alembic upgrade 0011
ruff check . --select E9,F63,F7,F82
python -m compileall -q .
bandit -r . -x tests -lll -iii
pip-audit -r requirements.txt
cd ../frontend
npm ci
npm run build
cd ..
APP_SECRET_KEY='release-check-secret-at-least-32-bytes' \
POSTGRES_PASSWORD='release-check-postgres-password' \
docker compose config -q
```

迁移往返会修改所连接数据库的 schema，只能在一次性测试库执行。完整 Compose 验收还要构建镜像、从空库迁移、启动 API/Worker/Frontend 并执行健康检查；具体顺序以根目录 [DEPLOYMENT.md](../DEPLOYMENT.md) 为准。

## v0.2.0 Graph 门禁

- `POST /api/cases/{case_id}/run-agents` 默认返回 `202 Accepted` 和真实持久化 `graph_run_id`。
- 同一 Case 重复调用返回活动运行；受权 `force_restart` 保留旧 Checkpoint、Evidence、Claim 和 Timeline并写审计。
- Evidence Request 经 Schema 校验后转为 Task，Probe 结果生成 Evidence/Message，并触发第二轮诊断。
- Critic 对假设执行 accept/revise/reject，根因确认满足证据来源、时效、反证和置信度阈值。
- Worker 中断后从过期租约和 Checkpoint 恢复，节点执行保持幂等。
- Budget Exhausted、凭据不可用、NetBox 设备缺失和证据冲突均进入可审计的停止/人工状态。
- Case 页面 Timeline、Hypothesis Board、Budget Panel 和 Graph 状态均读取真实 API，刷新后可恢复。
- Agent Tool Call 只允许 `agent_selectable=true` 且 `read_only=true` 的工具，并始终经过 Tool Registry、PolicyGuard 和 Probe Gateway。
- `AUTOMATION_OBSERVE_ONLY=True` 下不产生任何真实设备变更。

## 环境门禁

- 仅一个生产 PostgreSQL 逻辑数据库；测试库不得使用生产连接串。
- 数据库完成 `pg_dump -Fc` 备份，并在隔离实例成功恢复一次。
- OIDC/LDAP/SAML 至少一种 SSO 完成登录、登出、角色映射和身份源故障演练；本地紧急管理员凭据托管。
- 设备 SSH host key 全量入库；只读命令白名单和参数约束通过抽样检查。
- 通用 Webhook 接收端验证 HMAC、时间戳、事件 ID 幂等；死信告警和人工重投演练成功。
- ELK 代理保证 `(timestamp, document_id)` 稳定排序及 `search_after`；分页超过 1000 条无漏采、重采可去重。
- Zabbix/ELK 变更后验证可区分 verified、regressed、inconclusive；失败不会自动关闭 Case。

## Shadow Mode 门禁

至少连续 14 天保持 `AUTOMATION_OBSERVE_ONLY=true`：

- 严重事件误降噪数必须为 0；任何一条都阻断放量。
- checkpoint 无无法解释的倒退、跨页遗漏或长期滞后。
- 告警压缩率、Case 数量、人工误报/漏报标注均形成日报。
- Webhook 死信、Worker 心跳缺失、审批/执行异常均已接入告警。
- Agent Budget 耗尽、Tool Call 失败、Graph Resume、Case 状态转换、假设确认/拒绝和人工升级已接入指标与告警。
- 人工抽检确认冻结计划与实际命令、设备、参数完全一致。

只有门禁责任人签字后，才可按命令目录逐项开启变更能力；不得一次性关闭 observe-only。

## 当前发布结论

仓库实现完成后仍处于“候选生产版本”。服务器安装、真实 SSO/ELK/Zabbix/设备/Webhook 联调、恢复演练及 14 天 Shadow Mode 未完成前，不能宣称生产级可用。
