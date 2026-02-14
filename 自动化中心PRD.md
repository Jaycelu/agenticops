---

# 一、你现在要做的不是「自动化运维」，而是「自动化研判（Automated Diagnosis）」

这是一个非常关键的定性。

你当前现网环境具备以下特征：

* 现网稳定运行
* 告警以**状态变化**为主（Up/Down / Neighbor / BFD / CRC）
* 大量告警**不等于故障**
* 真正有价值的是：

  * 是否需要处理
  * 是配置问题、链路问题还是硬件问题
  * 给工程师一个“判断结论 + 行动建议”

👉 **这类自动化在行业中的标准定位是：**

> **AIOps – Automated Diagnosis & Recommendation**
> （自动化诊断与处置建议，而非自动化执行）

---

# 二、研判型自动化的核心设计原则（非常重要）

你这类自动化，必须满足 5 个原则：

## 2.1 不主动改配置（默认零破坏）

* 自动化只做：

  * 采集
  * 判断
  * 推理
  * 建议
* 所有“写操作”：

  * 需要明确审批
  * 且后置（不是当前阶段核心）

---

## 2.2 事件驱动 + 状态累积，而不是单条告警

这是你现在手动分析的本质：

> **“不是某一条日志有问题，而是一段时间的状态异常”**

所以自动化必须是：

* 基于 **时间窗口**
* 基于 **趋势**
* 基于 **多证据融合**

---

## 2.3 自动化的“输出物”不是动作，而是结论

研判型自动化的最终输出应该是：

* 问题类型判断（硬件 / 链路 / 配置 / 对端）
* 可信度（High / Medium / Low）
* 建议动作（检查项清单）

---

# 三、研判型自动化的标准技术链路（与你架构完全匹配）

我用你现在的系统资源来描述，不引入新平台。

---

## 3.1 自动化链路总览

```
日志 / 告警（ELK）
 ↓
状态聚合（时间窗口）
 ↓
设备数据补充（NetBox + CLI 配置）
 ↓
规则初判（确定是否值得 AI）
 ↓
AI 综合研判
 ↓
结论 & 建议
 ↓
自动化中心展示 + 钉钉推送
```

---

# 四、核心逻辑拆解（重点）

## 4.1 状态型告警 ≠ 自动化任务

你现在要做的是：

> **把“状态变化”升级为“状态异常”**

### 示例

| 告警                | 是否直接触发 |
| ----------------- | ------ |
| 接口 Down 一次        | ❌      |
| 接口 10 分钟 flap 8 次 | ✅      |
| CRC 单次增长          | ❌      |
| CRC 连续 24 小时增长    | ✅      |

👉 这一步叫：**状态聚合（State Aggregation）**

---

## 4.2 状态聚合模块（你自动化的第一道闸门）

### 输入

* log_sample
* 指标：

  * CRC errors
  * input errors
  * flap count
  * up/down duration

### 输出

```
{
  "device": "SW-Core-01",
  "interface": "XGE1/0/1",
  "abnormal_type": "LINK_QUALITY_DEGRADE",
  "evidence": {
    "crc_increase": true,
    "error_rate": "持续上升",
    "duration": "48h"
  }
}
```

---

## 4.3 设备上下文补充（这是你区别于普通 AIOps 的地方）

这一点你**已经具备基础能力**：

### 自动补充信息

* NetBox：

  * 设备角色
  * 所属基地
  * 连接关系（对端设备）
* 配置采集：

  * 接口配置
  * 光模块类型
  * 是否做过限速 / QoS / 错误抑制

👉 **这是 AI 判断“硬件 vs 配置”的关键证据**

---

## 4.4 规则初判（避免 AI 滥用）

在调用 AI 前，先做一层工程规则判断：

| 条件                  | 初步判断 |
| ------------------- | ---- |
| CRC + 无策略配置         | 偏硬件  |
| CRC + storm-control | 偏配置  |
| CRC + 双端同时          | 偏链路  |
| CRC + 单端            | 偏光模块 |

规则命中后再进入 AI。

---

# 五、AI 在你系统中的“正确位置”

你这个系统里，**AI 不是告警生成器**，而是：

> **“资深网络专家的思维放大器”**

---

## 5.1 AI 输入（必须是结构化证据）

```
【异常描述】
接口 XGE1/0/1 CRC 错误持续增长

【时间范围】
过去 48 小时

【设备信息】
核心交换机，承载生产网络

【接口配置】
无策略，无限速，无 QoS

【对端情况】
对端接口无错误

【历史行为】
近 30 天无配置变更
```

---

## 5.2 AI 输出（标准模板）

```
【问题判断】
高度可能为光模块或物理链路问题

【判断依据】
1. CRC 错误持续增长
2. 配置侧无异常
3. 对端未出现对等错误

【建议处理】
1. 检查光模块是否老化或接触不良
2. 更换光模块或光纤跳线验证
3. 若更换后问题消失，可确认为硬件故障

【风险等级】
中

【是否建议自动处置】
否（需人工确认）
```

---

# 六、自动化中心在当前阶段应该“长什么样”

你现在这个阶段，自动化中心的**核心价值**是：

* 帮你“提前判断”
* 帮你“减少无效告警”
* 帮你“统一分析思路”

---

## 6.1 自动化任务类型（建议定义）

| 类型      | 说明                    |
| ------- | --------------------- |
| 状态异常研判  | CRC / flap / neighbor |
| 稳定性趋势分析 | 长周期问题                 |
| 设备健康评估  | 汇总型                   |
| 告警降噪    | 合并 & 去重               |

---

## 6.2 自动化任务状态流（与你前面一致）

```
DETECTED → ANALYZED → REPORTED
```

不需要 RUNNING / EXECUTE。

---

# 七、为什么你现在不该做“自动改配置”

你这个判断是**非常成熟的**：

* 配置变更：

  * 高风险
  * 强依赖现场理解
* 当前价值密度：

  * 远低于“自动研判”

等做到：

* 研判准确率 > 90%
* 建议与人工判断一致性高

**再考虑半自动执行是完全正确的路线。**

---

# 八、结论（重点）

你现在自动化中心的核心使命应该是：

> **“让工程师少看设备、多看结论”**

而不是：

> “让系统替工程师改配置”



# 一、项目背景与目标

## 1.1 背景现状（As-Is）

当前系统具备以下能力：

* 日志来源：

  * 第三方系统（设备日志、平台日志、业务日志）
  * 多基地、多网络区域
* 能力现状：

  * 日志分析需**人工触发**
  * Zabbix 已完成告警 → 钉钉自动推送
* 核心问题：

  * ❌ 无统一数据持久化
  * ❌ 自动化无状态、不可追溯
  * ❌ 分析结果不可复用
  * ❌ 无“自动化任务视角”的管理与展示

**结论**：
当前系统属于**“任务调度 + 辅助分析”**，尚未形成真正意义上的**运维自动化系统**。

---

## 1.2 To-Be 目标

建设一个具备以下特征的自动化平台：

1. **数据先行**

   * 所有日志、分析结果、自动化决策均持久化
2. **策略驱动**

   * 自动化不依赖人工触发，而由规则 / 策略驱动
3. **状态可追溯**

   * 自动化每一步均可审计、回溯、复盘
4. **人只做决策**

   * 人工只介入高风险、需确认动作
5. **前后端解耦**

   * 后端自动化逻辑独立运行
   * 前端仅做展示与策略配置

---

# 二、整体架构设计

## 2.1 总体架构图（逻辑）

```
┌──────────────┐
│ 第三方数据源 │
│ (日志/接口) │
└──────┬───────┘
       │
       ▼
┌────────────────────┐
│ 日志采集 & 采样层  │
│ - 基地维度          │
│ - 条件过滤          │
└──────┬─────────────┘
       │
       ▼
┌────────────────────┐
│ 数据持久化层       │
│ PostgreSQL          │
│ - automation_state │
│ - raw_log_*        │
│ - analysis_result  │
└──────┬─────────────┘
       │
       ▼
┌────────────────────┐
│ 自动化决策引擎     │
│ - 规则判断         │
│ - LLM 分析         │
│ - 策略匹配         │
└──────┬─────────────┘
       │
       ▼
┌────────────────────┐
│ 自动化执行引擎     │
│ - 脚本              │
│ - API               │
│ - 需确认操作        │
└──────┬─────────────┘
       │
       ▼
┌────────────────────┐
│ 告警 & 结果输出     │
│ - 钉钉               │
│ - 自动化记录        │
└────────────────────┘
```

---

# 三、数据持久化架构设计（核心）

## 3.1 设计原则

* **以自动化为核心建模，而非日志**
* 多基地**逻辑隔离、物理可共享**
* 所有自动化行为都有状态

---

## 3.2 automation_state 数据库设计（PostgreSQL）

### 3.2.1 基地表 `site`

```sql
CREATE TABLE site (
    id SERIAL PRIMARY KEY,
    site_code VARCHAR(50) UNIQUE NOT NULL,
    site_name VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT now()
);
```

---

### 3.2.2 自动化任务定义表 `automation_task`

```sql
CREATE TABLE automation_task (
    id SERIAL PRIMARY KEY,
    task_code VARCHAR(100) UNIQUE NOT NULL,
    task_name VARCHAR(200),
    task_type VARCHAR(50), -- 巡检 / 日志分析 / 自愈
    risk_level VARCHAR(20), -- low / medium / high
    auto_execute BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMP DEFAULT now()
);
```

---

### 3.2.3 自动化策略表 `automation_policy`

```sql
CREATE TABLE automation_policy (
    id SERIAL PRIMARY KEY,
    task_id INT REFERENCES automation_task(id),
    site_id INT REFERENCES site(id),
    trigger_type VARCHAR(50), -- schedule / event / threshold
    trigger_condition JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now()
);
```

---

### 3.2.4 自动化运行状态表 `automation_state`

```sql
CREATE TABLE automation_state (
    id SERIAL PRIMARY KEY,
    task_id INT REFERENCES automation_task(id),
    policy_id INT REFERENCES automation_policy(id),
    site_id INT REFERENCES site(id),

    state VARCHAR(30), 
    -- pending / running / waiting_confirm / success / failed / aborted

    decision_result JSONB,
    execution_result JSONB,
    need_human_confirm BOOLEAN DEFAULT false,

    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);
```

---

### 3.2.5 原始日志表（按基地分区）

```sql
CREATE TABLE raw_log (
    id BIGSERIAL,
    site_id INT,
    log_time TIMESTAMP,
    source VARCHAR(100),
    level VARCHAR(20),
    content TEXT
) PARTITION BY LIST (site_id);
```

> 每个基地一张分区表，保证：

* 查询性能
* 数据隔离
* 后期独立归档

---

### 3.2.6 分析结果表

```sql
CREATE TABLE analysis_result (
    id SERIAL PRIMARY KEY,
    site_id INT,
    related_log_ids BIGINT[],
    summary TEXT,
    severity VARCHAR(20),
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT now()
);
```

---

# 四、日志采样与自动化判断

## 4.1 日志采样逻辑

* 基于你现有的**日志筛选条件**
* 增加一层：

  * `site_id`
  * `time_window`
  * `pattern`

示例：

```json
{
  "site": "NJ-BASE",
  "time_window": "5m",
  "include": ["ERROR", "LINK_DOWN"],
  "exclude": ["DEBUG"]
}
```

---

## 4.2 自动化判断流程

1. 日志进入 raw_log
2. 触发策略（定时 / 事件）
3. 自动分析（规则 + LLM）
4. 输出分析结果
5. 匹配自动化任务
6. 判断：

   * 是否可自动执行
   * 是否需人工确认

---

# 五、自动化执行与告警设计

## 5.1 Zabbix 告警处理策略

* **保留 Zabbix**
* **但不再作为自动化中枢**
* 新告警来源：

  * 自动化失败
  * 自动化异常
  * 高风险操作待确认

---

## 5.2 自动化告警类型

| 类型   | 说明          |
| ---- | ----------- |
| 执行失败 | 脚本 / API 失败 |
| 风险确认 | 需要人工批准      |
| 异常决策 | 分析不确定       |
| 自愈成功 | 可选通知        |

---

# 六、前端产品设计（PRD 重点）

## 6.1 模块划分

### 6.1.1 保留模块

* 日志查询 / 分析（现有）

---

### 6.1.2 新增模块：自动化中心

#### 1）自动化总览

* 今日执行次数
* 成功率
* 待确认任务
* 各基地统计

#### 2）自动化任务管理

* 任务列表
* 风险等级
* 是否自动执行

#### 3）策略管理

* 基地维度
* 触发条件
* 启停控制

#### 4）执行记录

* 时间线
* 状态流转
* 输入 / 输出

---

# 七、实施任务清单与周期

## 7.1 阶段划分

### Phase 1：基础能力（4 周）

* PostgreSQL 数据模型落地
* 日志入库（带 site_id）
* automation_state 主流程

---

### Phase 2：自动化决策（3 周）

* 规则引擎
* LLM 接入
* 决策结果持久化

---

### Phase 3：自动化执行（3 周）

* 脚本 / API 执行框架
* 风险确认机制
* 告警推送

---

### Phase 4：前端自动化中心（2 周）

* 自动化总览
* 策略管理
* 执行记录

---

---

# 一、ER 图（Entity Relationship Diagram）

> 说明：
>
> * 以 **automation_state 数据库**为核心
> * 多基地通过 `site_id` 贯穿
> * 与 NetBox 通过 `netbox_device_id` 做逻辑关联（不做物理外键）

---

## 1.1 ER 图（文本版）

```
┌──────────┐
│  site    │
│──────────│
│ id (PK)  │
│ site_code│
│ site_name│
└────┬─────┘
     │
     │1
     │
     │N
┌────▼──────────────┐
│ device_state      │
│──────────────────│
│ id (PK)           │
│ netbox_device_id  │
│ site_id (FK)      │
│ health_score      │
│ health_level      │
│ abnormal_flags[]  │
└────┬──────────────┘
     │
     │1
     │
     │N
┌────▼──────────────┐
│ log_sample        │
│──────────────────│
│ id (PK)           │
│ netbox_device_id  │
│ site_id (FK)      │
│ error_count       │
│ flap_count        │
│ sampled_at        │
└────┬──────────────┘
     │
     │1
     │
     │N
┌────▼─────────────────────┐
│ log_analysis_result      │
│─────────────────────────│
│ id (PK)                  │
│ netbox_device_id         │
│ site_id (FK)             │
│ analysis_type            │
│ confidence               │
│ summary                  │
│ related_sample_id (FK)   │
└──────────┬───────────────┘
           │
           │N
           │
           │1
┌──────────▼──────────────┐
│ automation_policy       │
│────────────────────────│
│ id (PK)                 │
│ site_id (FK)            │
│ condition (JSONB)       │
│ action (JSONB)          │
│ risk_level              │
│ require_confirm         │
└──────────┬──────────────┘
           │
           │1
           │
           │N
┌──────────▼──────────────┐
│ automation_task         │
│────────────────────────│
│ id (PK)                 │
│ policy_id (FK)          │
│ netbox_device_id        │
│ site_id (FK)            │
│ status                  │
│ triggered_by            │
│ started_at              │
│ finished_at             │
└──────────┬──────────────┘
           │
           │1
           │
           │N
┌──────────▼──────────────┐
│ automation_action_log   │
│────────────────────────│
│ id (PK)                 │
│ task_id (FK)            │
│ action_type             │
│ executor                │
│ result                  │
│ executed_at             │
└──────────┬──────────────┘
           │
           │0..1
           │
┌──────────▼──────────────┐
│ automation_approval     │
│────────────────────────│
│ id (PK)                 │
│ task_id (FK)            │
│ approver                │
│ decision                │
│ decided_at              │
└─────────────────────────┘
```

---

# 二、PRD 拆解为 Jira 任务（可直接导入）

以下按 **Epic → Story → Task** 结构输出。

---

## Epic 1：自动化数据持久化基础

### Story 1.1：automation_state 数据库建设

* Task 1.1.1：创建 site 表
* Task 1.1.2：创建 device_state 表
* Task 1.1.3：创建 log_sample 表
* Task 1.1.4：创建 log_analysis_result 表
* Task 1.1.5：创建 automation_policy 表
* Task 1.1.6：创建 automation_task 表
* Task 1.1.7：创建 automation_action_log 表
* Task 1.1.8：创建 automation_approval 表
* Task 1.1.9：设计索引（site_id / netbox_device_id）

---

## Epic 2：日志采样与分析自动化

### Story 2.1：日志采样服务

* Task 2.1.1：定义基地与日志筛选条件映射（site → filter）
* Task 2.1.2：实现 ELK 日志采样任务（定时）
* Task 2.1.3：采样结果写入 log_sample
* Task 2.1.4：采样异常处理与日志

---

### Story 2.2：AI 日志分析

* Task 2.2.1：定义可分析的日志场景类型
* Task 2.2.2：实现采样阈值判断逻辑
* Task 2.2.3：触发 AI 分析接口
* Task 2.2.4：分析结果写入 log_analysis_result

---

## Epic 3：自动化策略与决策引擎

### Story 3.1：策略模型实现

* Task 3.1.1：设计 policy condition JSON 规范
* Task 3.1.2：设计 action JSON 规范
* Task 3.1.3：策略启停控制逻辑

---

### Story 3.2：自动化决策引擎

* Task 3.2.1：定时扫描 log_analysis_result
* Task 3.2.2：匹配 automation_policy
* Task 3.2.3：创建 automation_task
* Task 3.2.4：状态流转（pending → running → done）

---

## Epic 4：自动化执行与审计

### Story 4.1：自动化执行引擎

* Task 4.1.1：统一脚本执行接口
* Task 4.1.2：执行结果结构化
* Task 4.1.3：失败重试策略

---

### Story 4.2：高危操作确认

* Task 4.2.1：高风险策略 require_confirm 逻辑
* Task 4.2.2：创建 automation_approval
* Task 4.2.3：确认后继续执行 / 终止

---

## Epic 5：前端自动化中心（新增）

---

# 三、前端页面原型结构（IA）

> 前端**不改你现有日志模块**
> 新增一个一级菜单：**自动化中心**

---

## 3.1 自动化中心 – 页面结构

```
自动化中心
├── 总览 Dashboard
│   ├── 今日自动化任务数
│   ├── 成功 / 失败 / 待确认
│   ├── 各基地统计
│
├── 自动化任务
│   ├── 任务列表
│   │   ├── 触发原因
│   │   ├── 当前状态
│   │   ├── 风险等级
│   ├── 任务详情页
│       ├── 输入条件
│       ├── 决策过程
│       ├── 执行动作
│       ├── 执行日志
│
├── 自动化策略
│   ├── 策略列表（按基地）
│   ├── 策略编辑
│   │   ├── 触发条件（JSON 表单）
│   │   ├── 动作定义
│   │   ├── 是否自动执行
│
├── 高危操作确认
│   ├── 待确认列表
│   ├── 批准 / 拒绝
│
└── 自动化审计
    ├── 操作记录
    ├── 人工介入记录
```

---

# 四、后端逻辑链路（端到端）

## 4.1 日志 → 自动化链路

```
ELK
 ↓（定时采样，按 site 过滤）
log_sample
 ↓（阈值判断）
AI 分析
 ↓
log_analysis_result
 ↓
policy matcher
 ↓
automation_task
 ↓
automation_action_log
 ↓
（可选）automation_approval
```

---

## 4.2 与 NetBox 的关系

* 只读：

  * device_id
  * site
  * role
* 回写（后期）：

  * 自动化标签
  * 最近自动化状态

---
