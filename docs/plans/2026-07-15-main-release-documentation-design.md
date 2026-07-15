# Main 分支发布与部署文档收口设计

## 目标

将已经通过 CI 的阶段 1–7 实现安全合并到 `main`，同时让首次部署者能够明确区分必须修改、按需修改和禁止提前修改的配置，并能完成安装、初始化、验收、升级与回滚。

## 文档结构

- `README.md`：项目状态、能力边界和可复制的十分钟 Docker Compose 快速部署。
- `DEPLOYMENT.md`：唯一的端到端安装手册，覆盖新装、旧库接管、管理员初始化、集成配置、升级和卸载。
- `docs/PRODUCTION_DEPLOYMENT.md`：生产运行手册，覆盖备份恢复、监控告警、故障回滚、Shadow Mode 和渐进放量。
- `docs/RUNBOOK.md`：接口联调和日常排障，不重复安装步骤。

## 配置分级

部署手册必须把配置分为三类：

1. 必须修改：`APP_SECRET_KEY`、`POSTGRES_PASSWORD`、`AUTH_PUBLIC_BASE_URL`、`FRONTEND_URL`。
2. 按需修改：NetBox、ELK、Zabbix、LLM、端口、日志、Webhook HTTP 策略。
3. 首次部署禁止关闭：`AUTOMATION_OBSERVE_ONLY=true`、`AUTH_COOKIE_SECURE=true`（HTTPS 生产环境）。

同时说明系统只使用一个生产 PostgreSQL 逻辑数据库；CI 测试库不是第二个生产数据库。

## 部署流程

标准流程为：检查主机与 DNS/TLS → 复制根目录 `.env` → 生成随机密钥 → 校验 Compose → 启动 PostgreSQL → 显式执行 Alembic → 启动 API/Worker/前端 → 创建唯一的紧急管理员 → 配置 SSO 与外部集成 → 检查健康端点和指标 → 进入至少 14 天 Shadow Mode。

已有数据库使用独立的 Alembic baseline 接管流程，不能与全新安装步骤混用。日常升级必须先备份，再拉取代码、构建镜像、执行迁移和逐服务验证。

## 合并安全

主工作区的未提交内容先保存为带名称的 stash。旧测试删除和测试依赖拆分已经由新测试体系覆盖，不再重复提交；新的 `pytest.ini` 必须保留。被 Git 跟踪的 `.DS_Store` 删除后提交。功能分支通过测试后推送，再将 `main` 快进到功能分支并推送远端。

## 验收

- Markdown 中的命令、路径、服务名与 Compose 实际定义一致。
- Compose 配置校验、后端测试、前端构建、静态检查和安全审计通过。
- 本地 `main`、远端 `main` 和功能分支最终指向同一提交。
- 主工作区干净，原未提交内容仍有 stash 备份可追溯。
