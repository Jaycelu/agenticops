# NetOps BS 项目结构与改造任务清单

## 1. 项目目录结构梳理

### 根目录
- `backend/`：后端服务（FastAPI + Agent + MCP + 自动化中心）
- `frontend/`：前端应用（Vue3）
- `storage/`：采样结果、模板、报告等本地数据
- `deploy/`：部署与启动脚本
- `docs/`：设计与改造文档
- `scripts/`：运维辅助脚本

### backend 核心子目录
- `backend/api/`：REST API 路由（chat、automation、alerts、assets、logs）
- `backend/agent/`：工作台对话 Agent（intent/planner/executor/orchestrator）
- `backend/mcp/`：NetBox/Zabbix/ELK 工具封装
- `backend/services/`：自动化中心核心能力（采样、异常跟踪、研判、决策、执行）
- `backend/models/`：LLM 客户端与 Prompt 模板
- `backend/config/`：配置和日志
- `backend/storage/`：会话存储

### frontend 核心子目录
- `frontend/src/pages/`：工作台、自动化中心等页面
- `frontend/src/api/`：前端 API 封装
- `frontend/src/store/`：Pinia 状态管理
- `frontend/src/router/`：路由配置

## 2. 本轮改造任务清单

1. `T1`：增强工作台意图识别，增加置信度与澄清机制（降低误调度）
2. `T2`：修复 Agent 计划与执行能力不一致问题（backup/inspection/healthcheck 不再直接失败）
3. `T3`：修复自动化中心站点阈值硬编码（按 site_id 动态加载阈值）
4. `T4`：修复异常类型阈值配置键不一致（避免判定偏差）
5. `T5`：清理核心链路调试输出，统一日志风格（提升可观测性）
6. `T6`：完成基础验证（语法级检查）

## 3. 执行顺序

按 `T1 -> T2 -> T3 -> T4 -> T5 -> T6` 依次执行。

## 4. 第二阶段任务（已执行）

7. `T7`：异常跟踪器持久化（内存态改为数据库）
8. `T8`：人工反馈闭环（任务级“正确/误判/部分正确”）
9. `T9`：反馈驱动风险校准（误判率高时自动降置信并强制人工确认）
10. `T10`：手动触发API与前端参数对齐 + 看板新增反馈质量指标
11. `T11`：反馈统计详情页（按诊断类型展示正确率趋势）
12. `T12`：自动化 API schema 层拆分（请求/响应模型统一）
13. `T13`：反馈洞察能力（误判TopN+调整建议）与按基地/诊断类型策略化配置
14. `T14`：反馈统计详情页增强（诊断类型切换、折线趋势、CSV导出）
15. `T15`：趋势图双指标切换（正确率/误判率/双线）+ CSV附带TopN建议
16. `T16`：反馈统计支持自定义日期范围（start_date/end_date）并与窗口模式兼容
