# NetOps Source-Centric AgenticOps 优化设计

日期：2026-03-08

## 1. 设计目标

将当前已经完成基础重构的 AgenticOps 平台，进一步优化为“真实数据源驱动 + 统一事件中心 + 多 Agent 降噪与分流”的运维系统。

这次优化强调三点：

- 唯一真实资产上下文来自 NetBox
- 唯一日志事实来自 ELK
- 唯一告警与实时状态来自 Zabbix

同时调整 SSH 的定位：

- SSH 不再参与默认诊断和智能体取证
- SSH 仅作为人工维护或自动化执行阶段的操作通道

平台最终目标：

- 对告警进行统一降噪
- 缩短 MTTR
- 降低人工介入比例
- 让 AgenticOps 真正成为“多源证据融合 + 自动判定 + 自动分流”的系统

## 2. 核心原则

### 2.1 数据源原则

- NetBox 是唯一真实资产、站点、设备、角色、拓扑源
- ELK 是唯一日志源
- Zabbix 是唯一告警与实时状态源
- SSH 不是默认证据源

### 2.2 事件原则

- 事件中心不是单一数据源页面
- 事件中心是统一事件工作台
- 事件中心汇总两类核心事件：
  - `log_signal_event`
  - `zabbix_alert_event`

### 2.3 Agent 原则

- Agent 不直接查询任意原始系统自由发挥
- Agent 只能使用标准化证据对象推理
- Agent 必须优先完成降噪、聚类、关联、分流，而不是默认升级到 Case

### 2.4 自动化原则

- 自动化的第一目标不是“尽快执行命令”
- 自动化的第一目标是降低噪声和缩短定位时间
- 默认流程应尽可能基于 NetBox + ELK + Zabbix 完成判定

## 3. 模块边界

### 3.1 数据源模块

#### 资产拓扑

- 数据源：NetBox
- 职责：
  - 展示站点、设备、角色、链路、拓扑
  - 为事件和 Case 提供唯一真实上下文

#### 日志中心

- 数据源：ELK
- 职责：
  - 日志范围查询
  - 设备日志采样
  - 日志聚合
  - 日志信号生成
- 输出：
  - `log_signal_event`

#### Zabbix 中心

- 数据源：Zabbix
- 职责：
  - 展示主机状态
  - 展示触发器与活跃问题
  - 展示实时异常状态
- 输出：
  - `zabbix_alert_event`

### 3.2 工作台模块

#### 事件中心

- 统一事件工作台
- 输入：
  - `log_signal_event`
  - `zabbix_alert_event`
- 职责：
  - 去重
  - 降噪
  - 聚类
  - 关联
  - 初判
  - 决定是否进入 Case / 工单 / 直接关闭

#### Case 中心

- 只承接值得深度分析和处置的问题
- 汇聚证据、Agent 结论、执行计划

#### 执行中心

- 修复计划、执行、验证、审计
- SSH 在这里作为执行通道出现，而不是默认诊断通道

#### 工单

- 人工闭环出口
- 适用于需要人工维护窗口、人工审批或跨系统协作的场景

#### 智能体中心 / 记忆中心

- 保持现有定位
- 但需要新增“降噪命中率、聚类命中率、直接工单率、Case 提升率”等指标

## 4. 运行逻辑

### 4.1 三源闭环

```text
NetBox -> 提供设备、站点、拓扑、归属关系
ELK -> 产生设备日志信号
Zabbix -> 产生告警与实时状态信号
       ↓
统一事件归一化
       ↓
事件中心（降噪/聚类/关联/优先级）
       ↓
多 Agent 协同判断
       ↓
Case 中心 或 工单系统 或 自动关闭
       ↓
执行中心 / 记忆系统
```

### 4.2 ELK 链路

- 日志中心不直接把原始日志视为告警
- 日志中心先形成设备级信号：
  - 异常签名激增
  - 多设备同签名扩散
  - 某站点同类模式聚合
  - 历史高风险 pattern 命中
- 这些信号进入事件中心，形成 `log_signal_event`

### 4.3 Zabbix 链路

- Zabbix 中心拉取：
  - 主机状态
  - 活跃问题
  - 触发器
  - 关键状态上下文
- 这些直接进入事件中心，形成 `zabbix_alert_event`

### 4.4 事件中心分流

事件中心对统一事件执行：

- 去重
- 聚类
- 日志信号和告警信号关联
- 设备/站点/拓扑关联
- 优先级重算

事件中心的输出只有三类：

- `noise`
- `ticket_only`
- `case_required`

## 5. SSH 定位调整

当前系统里 SSH 已经被接进默认 Case pipeline。

目标状态应调整为：

- 默认分析链路不自动拉 SSH 证据
- 无 SSH 凭据也不影响诊断
- 只有以下场景使用 SSH：
  - 执行修复计划
  - 人工维护窗口
  - 人工点击“进入维护/执行命令”

因此 SSH 从“数据源”降级为“执行通道”。

## 6. 数据模型建议

在现有 `source_event / case_record / evidence_item` 基础上继续收敛。

### 6.1 统一事件模型

建议在逻辑上统一为一个 `event_record`，至少包含：

- `event_type`
  - `log_signal`
  - `zabbix_alert`
- `source_system`
  - `elk`
  - `zabbix`
- `severity`
- `signal_key`
- `fingerprint`
- `site_id`
- `netbox_device_id`
- `device_ip`
- `host`
- `summary`
- `raw_payload`
- `normalized_payload`
- `correlation_keys`
- `status`

### 6.2 事件中心对象

- `event_cluster`
  - 事件聚类结果
- `event_decision`
  - 事件中心的降噪/分流结果

### 6.3 Case 保持不变

- `case_record`
- `agent_run`
- `agent_claim`
- `remediation_plan`
- `execution_run`
- `memory_entry`

## 7. 智能体职责重定义

### 7.1 Alert Triage Agent

- 输入：统一事件
- 输出：
  - 是否噪声
  - 是否需要聚类
  - 优先级
  - 是否需要进入 Case

### 7.2 Historical Analysis Agent

- 输入：事件摘要 + 历史记忆
- 输出：
  - 相似事件
  - 误报模式
  - 历史成功处置
  - 历史失败动作

### 7.3 Insight Analysis Agent

- 输入：ELK + Zabbix + NetBox
- 输出：
  - 根因假设
  - 影响面
  - 交叉验证结论
- 不再默认依赖 SSH

### 7.4 Autonomous Remediation Agent

- 输入：前三个 Agent 的结论
- 输出：
  - 关闭噪声
  - 建工单
  - 建 Case
  - 生成修复计划

## 8. 前端信息架构

左侧导航建议固定为：

- 驾驶舱
- 事件中心
- Case 中心
- 执行中心
- 智能体中心
- 记忆中心
- 日志中心
- Zabbix 中心
- 资产拓扑
- 工单
- 设置

页面职责：

- 日志中心：日志范围、日志聚合、日志信号
- Zabbix 中心：告警、主机状态、触发器、未关联事件
- 事件中心：统一事件流、降噪结果、聚类、Case/工单分流
- 工单：人工闭环

## 9. 优化目标与指标

### 9.1 目标

- Alert Noise Reduction
- MTTR Reduction
- Auto-Triage Rate
- Human Touch Reduction

### 9.2 驾驶舱指标

- 降噪率
- 自动分流率
- 直接工单率
- Case 提升率
- 平均 MTTR
- Zabbix 活跃告警数
- 未映射事件数
- 事件聚类命中率

## 10. 任务清单

### 阶段 1：架构语义与文档统一

- 更新设计文档与 README
- 将 NetBox/ELK/Zabbix 明确为主数据源
- 将 SSH 明确为执行通道
- 明确事件中心为统一事件工作台

验收标准：

- 文档、README、前端文案一致

### 阶段 2：后端统一事件流重构

- 新增或收敛统一事件模型
- 日志链路改为 `ELK -> signal -> event center`
- Zabbix 链路改为 `Zabbix -> alert -> event center`
- Case intake 改为只接收统一事件或人工触发

验收标准：

- 统一事件中心可以同时消费日志信号和 Zabbix 告警

### 阶段 3：默认诊断链路去 SSH 化

- 从默认 runtime context 中移除 SSH 证据采集
- `InsightAnalysisAgent` 不再默认依赖 SSH
- SSH 改为执行中心/人工维护通道

验收标准：

- 不配置 SSH 也能正常做事件判定和 Case 分析

### 阶段 4：事件中心重构

- 事件中心支持事件类型过滤：
  - `log_signal`
  - `zabbix_alert`
- 新增降噪、聚类、分流展示
- 支持直接关闭为噪声 / 建工单 / 进入 Case

验收标准：

- 事件中心不再只是简单事件列表

### 阶段 5：新增 Zabbix 中心

- 新增前端 `Zabbix` 页面
- 新增左侧导航入口
- 新增后端 Zabbix 查询接口
- 支持从 Zabbix 中心查看事件/Case/工单关联

验收标准：

- Zabbix 成为一等数据源模块

### 阶段 6：驾驶舱与工单口径重构

- 驾驶舱增加降噪和 MTTR 指标
- 工单增加来源类型
- 驾驶舱展示三源闭环健康度

验收标准：

- 驾驶舱指标能反映 AgenticOps 实际价值

## 11. 执行顺序建议

推荐执行顺序：

1. 阶段 1：文档和语义统一
2. 阶段 3：先去掉默认 SSH 诊断依赖
3. 阶段 2：统一事件流
4. 阶段 5：新增 Zabbix 中心
5. 阶段 4：重构事件中心
6. 阶段 6：重做驾驶舱与工单指标

## 12. 本次启动范围

本次从阶段 1 开始，并立刻推进阶段 3 的第一步：

- 文档和 README 先统一
- 默认 Case pipeline 中先移除 SSH 自动证据采集
- 为后续统一事件流和 Zabbix 中心留出清晰边界

## 13. 执行状态跟踪

### 已完成

- 阶段 1：已新增本设计文档，并同步更新总设计跟踪与 README
- 阶段 1：已将 NetBox / ELK / Zabbix 明确为主数据源，SSH 明确为执行通道
- 阶段 3：默认 `case pipeline` 已移除 SSH 自动证据采集
- 阶段 5：已新增 `Zabbix 中心` 前端页面、路由、导航入口
- 阶段 5：已新增 `/api/zabbix/status`、`/api/zabbix/alerts`、`/api/zabbix/sync-alerts`
- 阶段 2：事件 API 已显式返回 `event_type / source_category / source_label / signal_key / case_id / case_code`
- 阶段 2：日志聚合与设备日志分析已可写入 `log_signal` 事件到事件中心
- 阶段 2：Zabbix 当前可将告警同步写入统一事件表
- 阶段 2：日志采样主任务已在写入 `LogSample` 后自动沉淀聚合后的 `log_signal` 事件
- 阶段 4：事件中心前端已支持 `event_type / disposition` 过滤，并显示来源标签、事件类型、分流结果
- 阶段 4：事件 API 已补充 `disposition / disposition_reason / decision_confidence / cluster_key`
- 阶段 4：事件中心已支持手动将事件标记为 `noise`
- 阶段 4：已新增 `/api/events/clusters`，支持基于站点/设备/信号族的聚类与跨源关联
- 阶段 4：事件中心前端已新增聚类卡片，可按 `correlation_key` 查看同问题簇事件
- 阶段 4：事件簇已补充 `device_name / device_role / site_name / topology_hint / root_cause_candidate`
- 阶段 4：热点问题簇已补充实时拓扑邻接、链路数量与影响面估算
- 阶段 4：已新增 `/api/events/root-causes`，支持跨簇归并后的根因候选排序
- 阶段 4：事件中心与驾驶舱已新增“根因候选榜”视图
- 阶段 4：根因候选已补充优先级处置建议，并可从事件中心直接联动到 Case / 执行中心
- 阶段 5：Zabbix 中心已展示事件中心关联、Case 关联与工单关联入口
- 阶段 3：`Alert Triage Agent / Insight Analysis Agent` 已去除默认 SSH 诊断依赖语义
- 阶段 6：驾驶舱已切换到统一事件、降噪率、直接工单率、Case 提升率、数据源健康和热点问题簇口径
- 阶段 6：驾驶舱热点问题簇与根因候选已支持精确跳转到事件中心筛选视图

### 进行中

- 阶段 4：事件中心已具备统一事件分流、可解释问题簇和根因候选榜，但尚未完成更深入的拓扑影响面压缩与候选排序校准
- 阶段 6：驾驶舱已完成第一版 AgenticOps 指标切换，但 MTTR 仍是基于已关闭 Case 的近似估算

### 未开始

- 阶段 4：事件中心增加更深入的拓扑影响面压缩与候选排序校准
- 阶段 6：执行中心继续增强推荐动作与真实执行记录的联动
