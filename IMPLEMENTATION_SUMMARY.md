# AgenticOps 实施摘要

更新时间：2026-03-10

## 当前实现状态

项目当前的真实主链路已经收敛为：

```text
Event -> Case -> Multi-Agent -> Memory -> Fabric
```

前端为 `Vue 3 + Vite`，后端为 `FastAPI + SQLAlchemy + PostgreSQL`。

## 已落地的核心能力

- 统一事件入口与分流
- Case 工作台
- 多智能体分析
- 记忆中心
- 执行中心
- 数据源工作台：资产、日志、Zabbix、工单、设置

## 仓库说明

本文件用于保留公开版仓库的高层实现摘要，不再记录历史内网部署细节、旧前端方案或包含真实环境信息的实施日志。

如需了解当前对外文档，请优先阅读：

- `README.md`
- `DEPLOYMENT.md`
- `PORT_CONFIGURATION.md`
- `docs/plans/2026-03-10-readme-v1-design.md`
