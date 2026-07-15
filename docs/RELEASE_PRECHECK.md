# AgenticOps 生产发布门禁

代码合并、镜像构建成功只代表“可部署”，不代表已经达到生产认证。以下门禁必须在目标服务器与真实集成环境执行并留存证据。

## 自动门禁

- 后端单元测试、PostgreSQL 集成测试与 Alembic `check` 通过。
- Ruff、Bandit、pip-audit、Python compileall 通过。
- 前端 `npm ci && npm run build` 通过。
- `APP_SECRET_KEY`、`POSTGRES_PASSWORD` 注入后 `docker compose config -q` 通过。
- API `/health/ready`、Worker heartbeat 与 `/metrics` 可被监控系统采集。

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
- 人工抽检确认冻结计划与实际命令、设备、参数完全一致。

只有门禁责任人签字后，才可按命令目录逐项开启变更能力；不得一次性关闭 observe-only。

## 当前发布结论

仓库实现完成后仍处于“候选生产版本”。服务器安装、真实 SSO/ELK/Zabbix/设备/Webhook 联调、恢复演练及 14 天 Shadow Mode 未完成前，不能宣称生产级可用。
